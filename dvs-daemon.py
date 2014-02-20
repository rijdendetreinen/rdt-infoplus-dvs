#!/usr/bin/env python

"""
DVS daemon welke alle DVS berichten verwerkt en in geheugen opslaat.
"""

import sys
import os
import zmq
from gzip import GzipFile
from cStringIO import StringIO
import pytz
from datetime import datetime, timedelta
import cPickle as pickle
import argparse
import gc
import logging
import logging.config
import yaml
import threading

import infoplus_dvs

def setup_logging(default_path='logging.yaml',
    default_level=logging.INFO, env_key='LOG_CFG'):
    """
    Setup logging configuration
    """

    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as config_file:
            log_config = yaml.load(config_file.read())
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level=default_level)

def load_config(config_file_path='config/dvs-server.yaml'):
    """
    Setup logging configuration
    """

    global config

    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'rt') as config_file:
                config = yaml.load(config_file.read())
        except Exception as e:
            print "Fout in configuratiebestand. Foutmelding: %s" % e
            sys.exit(1)
    else:
        print "Configuratiebestand '%s' niet aanwezig" % config_file_path
        sys.exit(1)

def main():
    """
    Main loop
    """

    global station_store, trein_store, counters, locks, config

    # Maak output in utf-8 mogelijk in Python 2.x:
    reload(sys)
    sys.setdefaultencoding("utf-8")

    gc.set_debug(gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_INSTANCES | gc.DEBUG_OBJECTS)

    # Default config (nog naar losse configfile):
    dvs_server = "tcp://127.0.0.1:8100"
    dvs_client_bind = "tcp://0.0.0.0:8120"

    # Initialiseer argparse
    parser = argparse.ArgumentParser(description='RDT InfoPlus DVS daemon')

    parser.add_argument('-c', '--config', dest='configFile', default='config/dvs-server.yaml',
        action='store', help='Configuratiebestand')
    parser.add_argument('-ls', '--laad-stations', dest='laadStations',
        action='store_true', help='Laad station_store')
    parser.add_argument('-lt', '--laad-treinen', dest='laadTreinen',
        action='store_true', help='Laad trein_store')

    args = parser.parse_args()

    # Laad configuratie:
    load_config(args.configFile)

    # Stel logging in:
    log_config_file = None

    # Check of er een logger configuratie is opgegeven:
    if 'logging' in config and 'log_config' in config['logging']:
        log_config_file = config['logging']['log_config']
    
    # Stel logger in adhv config:
    setup_logging(log_config_file)

    # Geef logger instance:
    logger = logging.getLogger(__name__)
    logger.info('Server start op')

    # Verwerk configuratie:
    try:
        dvs_server = config['bindings']['dvs_server']
        dvs_client_bind = config['bindings']['client_server']
        injector_bind = config['bindings']['injector_server']
    except:
        logger.exception("Configuratiefout, server wordt afgesloten")
        sys.exit(1)

    # Initialiseer datastores:
    station_store = { }
    trein_store = { }

    # Initialiseer datastore locks
    locks = { }
    locks['trein'] = threading.Lock()
    locks['station'] = threading.Lock()

    # Initialiseer counters voor aantal verwerkte berichten,
    # aantal dubbele berichten, aantal verouderde berichten,
    # aantal keren GC op trein- en station store
    counters = {}
    counters['msg'] = 0
    counters['dubbel'] = 0
    counters['ouder'] = 0
    counters['gc_station'] = 0
    counters['gc_trein'] = 0
    counters['injecties'] = 0

    # Laad oude datastores in (indien gespecifeerd):
    if args.laadStations == True:
        station_store = laad_stations()

    if args.laadTreinen == True:
        trein_store = laad_treinen()

    # Socket to talk to server
    context = zmq.Context()

    # Start een nieuwe thread om client requests uit te lezen
    client_thread = ClientThread(dvs_client_bind)
    client_thread.daemon = True
    client_thread.start()

    # Start een nieuwe injector thread om client requests uit te lezen
    injector_thread = InjectorThread(injector_bind)
    injector_thread.daemon = True
    injector_thread.start()

    # Stel ZeroMQ in:
    server_socket = context.socket(zmq.SUB)
    server_socket.connect(dvs_server)
    server_socket.setsockopt(zmq.SUBSCRIBE, '')

    poller = zmq.Poller()
    poller.register(server_socket, zmq.POLLIN)

    # Registreer starttijd server:
    starttime = datetime.now()

    # Start nieuwe thread voor garbage collecting:
    gc_stopped = threading.Event()
    gc_thread = GarbageThread(gc_stopped)
    gc_thread.daemon = True
    gc_thread.start()

    #socks = dict(poller.poll())
    #print socks

    logger.info("Gereed voor ontvangen DVS berichten (van server %s)", dvs_server)

    try:
        while True:
            multipart = server_socket.recv_multipart()
            content = GzipFile('', 'r', 0 ,
                StringIO(''.join(multipart[1:]))).read()

            # Parse trein xml:
            try:
                trein = infoplus_dvs.parse_trein(content)

                rit_station_code = trein.rit_station.code
                
                if trein.status == '5':
                    # Trein vertrokken
                    # Verwijder uit station_store
                    if rit_station_code in station_store \
                    and trein.treinnr in station_store[rit_station_code]:
                        with locks['station']:
                            del(station_store[rit_station_code][trein.treinnr])

                    # Verwijder uit trein_store
                    if trein.treinnr in trein_store \
                    and rit_station_code in trein_store[trein.treinnr]:
                        del(trein_store[trein.treinnr][rit_station_code])
                        if len(trein_store[trein.treinnr]) == 0:
                            with locks['trein']:
                                del(trein_store[trein.treinnr])
                else:
                    # Maak item in trein_store indien niet aanwezig
                    if trein.treinnr not in trein_store:
                        with locks['trein']:
                            trein_store[trein.treinnr] = {}

                    # Maak item in station_store indien niet aanwezig:
                    if rit_station_code not in station_store:
                        with locks['station']:
                            station_store[rit_station_code] = {}

                    # Update of insert trein aan station store:
                    if trein.treinnr in station_store[rit_station_code]:
                        # Trein komt reeds voor in station store voor dit station
                        if trein.rit_timestamp > station_store[rit_station_code][trein.treinnr].rit_timestamp:
                            # Bericht is nieuwer, update store:
                            station_store[rit_station_code][trein.treinnr] = trein
                        elif trein.rit_timestamp == station_store[rit_station_code][trein.treinnr].rit_timestamp:
                            # Bericht is nieuwer, update store:
                            logger.info('Dubbel bericht ontvangen: %s == %s, niet verwerkt (trein %s/%s)',
                                trein.rit_timestamp, station_store[rit_station_code][trein.treinnr].rit_timestamp,
                                trein.treinnr, trein.rit_station.code)

                            # Update counter voor dubbele berichten:
                            counters['dubbel'] += 1
                        else:
                            # Bepaal 1 seconde treshold:
                            warn_treshold = station_store[rit_station_code][trein.treinnr].rit_timestamp - timedelta(seconds=5)
                            
                            # Warning log message indien treshold van 1 seconde overschreden is:
                            if trein.rit_timestamp <= warn_treshold:
                                log_level = logging.WARNING
                            else:
                                log_level = logging.INFO

                            logger.log(log_level, 'Ouder bericht ontvangen: %s < %s, niet verwerkt (trein %s/%s)',
                                trein.rit_timestamp, station_store[rit_station_code][trein.treinnr].rit_timestamp,
                                trein.treinnr, trein.rit_station.code)

                            # Update counter voor verouderde berichten:
                            counters['ouder'] += 1
                    else:
                        # Trein kwam op dit station nog niet voor, voeg toe:
                        station_store[rit_station_code][trein.treinnr] = trein

                    # Update of insert trein aan trein store:
                    if rit_station_code in trein_store[trein.treinnr]:
                        # Trein komt reeds voor in trein store voor dit treinnr
                        if trein.rit_timestamp > trein_store[trein.treinnr][rit_station_code].rit_timestamp:
                            # Bericht is nieuwer, update store:
                            trein_store[trein.treinnr][rit_station_code] = trein
                    else:
                        # Treinnr kwam op dit station nog niet voor, voeg toe:
                        trein_store[trein.treinnr][rit_station_code] = trein

            except infoplus_dvs.OngeldigDvsBericht:
                logger.error('Ongeldig DVS bericht')
                logger.debug('Ongeldig DVS bericht: %s', content)
            except Exception:
                logger.error(
                    'Fout tijdens DVS bericht verwerken', exc_info=True)
                logger.error('DVS crash bericht: %s', content)
                
            counters['msg'] += + 1


    except KeyboardInterrupt:
        logger.info('Shutting down...')

        server_socket.close()
        context.term()

        gc_stopped.set()

        logger.info("Saving station store...")
        pickle.dump(station_store, open('datadump/station.store', 'wb'), -1)

        logger.info("Saving trein store...")
        pickle.dump(trein_store, open('datadump/trein.store', 'wb'), -1)

        logger.info(
            "Statistieken: %s berichten verwerkt sinds %s", counters['msg'], starttime)

    except Exception:
        logger.error("Fout in main loop", exc_info=True)


def laad_stations():
    """
    Laad stations uit pickle dump
    """

    logger = logging.getLogger(__name__)

    logger.info('Inladen station_store...')
    station_store_file = open('datadump/station.store', 'rb')
    store = pickle.load(station_store_file)
    station_store_file.close()

    return store

def laad_treinen():
    """
    Laad treinen uit pickle dump
    """

    logger = logging.getLogger(__name__)

    logger.info('Inladen trein_store...')
    trein_store_file = open('datadump/trein.store', 'rb')
    store = pickle.load(trein_store_file)
    trein_store_file.close()

    return store

class ClientThread(threading.Thread):
    """
    Client thread voor verwerken requests van clients
    """

    logger = None
    dvs_client_bind = None

    def __init__ (self, dvs_client_bind):
        self.dvs_client_bind = dvs_client_bind
        self.logger = logging.getLogger(__name__)
        threading.Thread.__init__(self, name='ClientThread')

    def run(self):
        self.logger.info('Client thread gestart')
        
        context = zmq.Context()
        client_socket = context.socket(zmq.REP)
        client_socket.bind(self.dvs_client_bind)

        self.logger.info('Client thread gereed voor verbindingen (%s)', self.dvs_client_bind)
        
        while True:
            url = client_socket.recv()

            try:
                arguments = url.split('/')

                if arguments[0] == 'station' and len(arguments) == 2:
                    # Haal alle treinen op voor gegeven station
                    station_code = arguments[1].upper()
                    if station_code in station_store:
                        client_socket.send_pyobj(
                            station_store[station_code], zmq.NOBLOCK)
                    else:
                        client_socket.send_pyobj({})

                elif arguments[0] == 'trein' and len(arguments) == 2:
                    # Haal alle stations op voor gegeven trein
                    trein_nr = arguments[1]
                    if trein_nr in trein_store:
                        client_socket.send_pyobj(trein_store[trein_nr], zmq.NOBLOCK)
                    else:
                        client_socket.send_pyobj({})

                elif arguments[0] == 'store' and len(arguments) == 2:
                    # Haal de volledige datastore op...
                    if arguments[1] == 'trein':
                        # Volledige trein store:
                        client_socket.send_pyobj(trein_store, zmq.NOBLOCK)
                    elif arguments[1] == 'station':
                        # Volledige station store:
                        client_socket.send_pyobj(station_store, zmq.NOBLOCK)
                    else:
                        client_socket.send_pyobj(None)

                elif arguments[0] == 'count' and len(arguments) == 2:
                    # Haal de grootte van de store op:
                    if arguments[1] == 'trein':
                        # Grootte van trein store:
                        client_socket.send_pyobj(len(trein_store))
                    elif arguments[1] == 'station':
                        # Grootte van station store:
                        client_socket.send_pyobj(len(station_store))
                    elif arguments[1] in counters:
                        # Standaard counter:
                        client_socket.send_pyobj(counters[arguments[1]])
                    else:
                        # Onbekend type:
                        client_socket.send_pyobj(None)

                else:
                    # Standaard antwoord
                    client_socket.send_pyobj(None)
            except Exception:
                client_socket.send_pyobj(None)
                self.logger.exception('Fout bij sturen client respone')


# Garbage collection thread:
class GarbageThread(threading.Thread):
    """
    Thread die verantwoordelijk is voor garbage collection
    """

    stopped = None
    logger = None

    def __init__(self, event):
        threading.Thread.__init__(self, name='GarbageThread')
        self.logger = logging.getLogger(__name__)
        self.logger.info("GC thread geinitialiseerd")
        self.stopped = event

    def run(self):
        self.logger.info("Initiele garbage collecting")
        self.garbage_collect()

        while not self.stopped.wait(60):
            try:
                self.logger.info("Periodieke garbage collecting")
                self.garbage_collect()

                self.logger.info(
                    "Statistieken: station_store=%s, trein_store=%s"
                    % (len(station_store), len(trein_store)))
            except Exception:
                self.logger.error('Fout in GC thread', exc_info=True)

    def garbage_collect(self):
        """
        Garbage collecting.
        Ruimt alle treinen op welke nog niet vertrokken zijn, maar welke
        al wel 10 minuten weg hadden moeten zijn (volgens actuele vertrektijd)
        """

        global station_store, trein_store, counters

        # Bereken treshold:
        treshold = datetime.now(pytz.utc) - timedelta(minutes=10)
        treshold_statisch = datetime.now(pytz.utc)

        # Performance controle; start:
        start = datetime.now()
        verwerkte_items = 0

        # Check alle treinen in station_store:
        for station in station_store:
            try:
                for trein_rit, trein in station_store[station].items():
                    if (trein.statisch == False and trein.vertrek_actueel < treshold) \
                    or (trein.statisch == True and trein.vertrek_actueel < treshold_statisch):
                        try:
                            with locks['station']:
                                del(station_store[station][trein_rit])

                            verwerkte_items += 1

                            if trein.is_opgeheven():
                                # Voor opgeheven treinen komt geen wisbericht,
                                # daarom is het te verwachten dat deze GC'd worden
                                # Log alleen debug melding
                                self.logger.debug('GC [SS] Del %s/%s, opgeheven' % (trein_rit, station))
                            elif trein.statisch == True:
                                self.logger.debug('GC [SS] Del %s/%s, statisch' % (trein_rit, station))
                            else:
                                # Waarschuwing indien trein niet opgeheven, maar
                                # wel 10-minuten window overschreden:
                                self.logger.warn('GC [SS] Del %s/%s' % (trein_rit, station))

                                counters['gc_station'] = counters['gc_station'] + 1
                        except KeyError:
                            self.logger.debug('GC [SS] Al verwijderd %s/%s', trein_rit, station)
            except KeyError:
                self.logger.warn('GC [SS] Station verwijderd %s', station)

        # Bereken duur voor GC en duur per item
        if verwerkte_items > 0:
            duur = datetime.now() - start
            self.logger.info("GC [SS] * %s items verwerkt in %s (%s per verwerking)", verwerkte_items, duur, (duur / verwerkte_items))

        # Performance controle; start:
        start = datetime.now()
        verwerkte_items = 0

        # Check alle treinen in trein_store:
        for trein_rit in trein_store.keys():
            try:
                for station, trein in trein_store[trein_rit].items():
                    if (trein.statisch == False and trein.vertrek_actueel < treshold) \
                    or (trein.statisch == True and trein.vertrek_actueel < treshold_statisch):
                        try:
                            with locks['trein']:
                                del(trein_store[trein_rit][station])

                            verwerkte_items += 1

                            if trein.is_opgeheven():
                                # Voor opgeheven treinen komt geen wisbericht,
                                # daarom is het te verwachten dat deze GC'd worden
                                # Log alleen debug melding
                                self.logger.debug('GC [TS] Del %s/%s, opgeheven' % (trein_rit, station))
                            elif trein.statisch == True:
                                self.logger.debug('GC [TS] Del %s/%s, statisch' % (trein_rit, station))
                            else:
                                # Waarschuwing indien trein niet opgeheven, maar
                                # wel 10-minuten window overschreden:
                                self.logger.warn('GC [TS] Del %s/%s' % (trein_rit, station))

                                counters['gc_trein'] = counters['gc_trein'] + 1
                        except KeyError:
                            self.logger.debug('GC [TS] Al verwijderd %s/%s', trein_rit, station)
            except KeyError:
                self.logger.debug('GC [TS] Al verwijderd %s', trein_rit)

            # Verwijder treinen uit trein_store dict
            # indien geen informatie meer:
            if len(trein_store[trein_rit]) == 0:
                del(trein_store[trein_rit])

        # Bereken duur voor GC en duur per item
        if verwerkte_items > 0:
            duur = datetime.now() - start
            self.logger.info("GC [TS] * %s items verwerkt in %s (%s per verwerking)", verwerkte_items, duur, (duur / verwerkte_items))

        # Trigger Python GC na deze opruimronde:
        gc.collect()

        return


# Injector thread:
class InjectorThread(threading.Thread):
    """
    Thread die verantwoordelijk is voor garbage collection
    """

    logger = None
    injector_bind = None

    def __init__(self, injector_bind):
        threading.Thread.__init__(self, name='InjectorThread')
        self.logger = logging.getLogger(__name__)
        self.logger.info("Injector geinitialiseerd")
        self.injector_bind = injector_bind

    def run(self):
        # Bereid ZeroMQ voor:
        context = zmq.Context()
        client_socket = context.socket(zmq.REP)
        client_socket.bind(self.injector_bind)

        self.logger.info('Injector thread gereed (%s)', self.injector_bind)
        
        while True:
            try:
                # Ontvang injection dict
                trein_dict = client_socket.recv_pyobj()
                
                self.logger.debug("Nieuwe injectie: %s", trein_dict)
                counters['injecties'] += 1

                # Stuur response naar injector
                client_socket.send_pyobj(True)

                # Converteer ontvangen dict naar 
                trein = infoplus_dvs.parse_trein_dict(trein_dict, True)

                # Bepaal rit ID. Prefix 'i' om overlap met InfoPlus
                # DVS ID's te voorkomen.
                rit_id = 'i%s' % trein.rit_id

                # Voeg trein toe aan stores:
                with locks['trein']:
                    if rit_id not in trein_store:
                        trein_store[rit_id] = {}

                # Maak item in station_store indien niet aanwezig:
                with locks['station']:
                    if trein.rit_station.code not in station_store:
                        station_store[trein.rit_station.code] = {}

                # Voeg geinjecteerde trein toe aan station en trein stores:
                station_store[trein.rit_station.code][rit_id] = trein
                trein_store[rit_id][trein.rit_station.code] = trein

            except Exception:
                self.logger.exception("Fout tijdens verwerken injectie")

if __name__ == "__main__":
    main()