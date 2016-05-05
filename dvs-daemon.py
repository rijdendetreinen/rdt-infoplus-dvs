#!/usr/bin/env python

"""
InfoPlus DVS Daemon, voor het verwerken en opvragen van NS InfoPlus-DVS berichten.
Copyright (C) 2013-2016 Geert Wirken

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
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
import threading
from collections import deque
from Queue import Queue

import infoplus_dvs
import dvs_util


def main():
    """
    Main loop
    """

    global station_store, trein_store, counters, locks, configs, system_status, message_queue

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
    config = dvs_util.load_config(args.configFile)

    # Stel logging in:
    dvs_util.setup_logging(config)

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
    counters['msg_time'] = {}

    # Initialiseer system_status:
    system_status = {}
    system_status['status'] = 'UNKNOWN' # of DOWN of UP of RECOVERING
    system_status['down_since'] = None
    system_status['recovering_since'] = None

    # Laad oude datastores in (indien gespecifeerd):
    if args.laadStations == True:
        station_store = laad_stations()

    if args.laadTreinen == True:
        trein_store = laad_treinen()

    # Socket to talk to server
    context = zmq.Context()

    message_queue = Queue()

    keep_departures = False
    if 'debug' in config:
        if config['debug']['keep_departures'] == True:
            keep_departures = True
            logger.warn("Debug optie 'keep_departures' actief: ritten worden niet gewist")

    # Start een nieuwe thread om messages te verwerken
    worker_thread = WorkerThread(keep_departures)
    worker_thread.daemon = True
    worker_thread.start()

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

    # Stel envelope in:
    envelope = ''
    if 'zmq' in config and 'envelope' in config['zmq']:
        envelope = config['zmq']['envelope']

    server_socket.setsockopt(zmq.SUBSCRIBE, envelope)

    # Stel HWM in (fallback voor oude pyzmq versies):
    try:
        server_socket.setsockopt(zmq.RCVHWM, 0)
    except AttributeError:
        server_socket.setsockopt(zmq.HWM, 0)

    # Registreer starttijd server:
    starttime = datetime.now()

    # Start nieuwe thread voor garbage collecting:
    gc_stopped = threading.Event()
    gc_thread = GarbageThread(gc_stopped, config, keep_departures)
    gc_thread.daemon = True
    gc_thread.start()

    logger.info("Gereed voor ontvangen DVS berichten (van server %s), envelope: %s", dvs_server, envelope)

    try:
        while True:
            multipart = server_socket.recv_multipart()
            content = multipart[1:]
            message_queue.put(content)

    except KeyboardInterrupt:
        logger.info('Afsluiten...')

        server_socket.close()
        context.term()

        gc_stopped.set()

        logger.info("Station store opslaan...")
        pickle.dump(station_store, open('datadump/station.store', 'wb'), -1)

        logger.info("Trein store opslaan...")
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

class WorkerThread(threading.Thread):
    """
    Worker thread voor het verwerken van DVS berichten.
    """

    logger = None
    keep_departures = False

    def __init__ (self, keep_departures):
        self.logger = logging.getLogger(__name__)
        self.keep_departures = keep_departures
        threading.Thread.__init__(self, name='WorkerThread')

    def run(self):
        self.logger.info('Consumer thread gestart')

        while True:
            message = message_queue.get()
            content = GzipFile('', 'r', 0 ,
                StringIO(''.join(message))).read()

            # Parse trein xml:
            try:
                trein = infoplus_dvs.parse_trein(content)

                rit_station_code = trein.rit_station.code

                if trein.status == '5':
                    # Markeer als vertrokken, zodat er een timestamp op staat
                    trein.markeer_vertrokken()

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
                        self.logger.info('Dubbel bericht ontvangen: %s == %s, niet verwerkt (trein %s/%s)',
                            trein.rit_timestamp, station_store[rit_station_code][trein.treinnr].rit_timestamp,
                            trein.treinnr, trein.rit_station.code)

                        # Update counter voor dubbele berichten:
                        counters['dubbel'] += 1
                    else:
                        # Bepaal 1 seconde threshold:
                        warn_threshold = station_store[rit_station_code][trein.treinnr].rit_timestamp - timedelta(seconds=5)

                        # Warning log message indien threshold van 1 seconde overschreden is:
                        if trein.rit_timestamp <= warn_threshold:
                            log_level = logging.WARNING
                        else:
                            log_level = logging.INFO

                        self.logger.log(log_level, 'Ouder bericht ontvangen: %s < %s, niet verwerkt (trein %s/%s)',
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
                self.logger.error('Ongeldig DVS bericht')
                self.logger.debug('Ongeldig DVS bericht: %s', content)
            except Exception:
                self.logger.error(
                    'Fout tijdens DVS bericht verwerken', exc_info=True)
                self.logger.error('DVS crash bericht: %s', content)
                
            counters['msg'] += + 1

            pass


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
                        with locks['station']:
                            client_socket.send_pyobj(
                                {'status': system_status,
                                'data': station_store[station_code]},
                                zmq.NOBLOCK)
                    else:
                        client_socket.send_pyobj({})

                elif arguments[0] == 'trein' and len(arguments) == 2:
                    # Haal alle stations op voor gegeven trein
                    trein_nr = arguments[1]
                    if trein_nr in trein_store:
                        with locks['trein']:
                            client_socket.send_pyobj(
                                {'status': system_status,
                                'data': trein_store[trein_nr]}, zmq.NOBLOCK)
                    else:
                        client_socket.send_pyobj({})

                elif arguments[0] == 'store' and len(arguments) == 2:
                    # Haal de volledige datastore op...
                    if arguments[1] == 'trein':
                        # Volledige trein store:
                        with locks['trein']:
                            client_socket.send_pyobj(trein_store, zmq.NOBLOCK)
                    elif arguments[1] == 'station':
                        # Volledige station store:
                        with locks['station']:
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

                elif arguments[0] == 'status':
                    # Stuur statusinformatie terug:
                    if len(arguments) == 2 and arguments[1] == 'status':
                        client_socket.send_pyobj(system_status['status'])
                    else:
                        client_socket.send_pyobj(system_status)

                else:
                    # Standaard antwoord
                    client_socket.send_pyobj(None)
            except Exception:
                client_socket.send_pyobj(None)
                self.logger.exception('Fout bij sturen client response')


# Garbage collection thread:
class GarbageThread(threading.Thread):
    """
    Thread die verantwoordelijk is voor garbage collection
    """

    stopped = None
    logger = None
    msg_count_queue = None

    count_time_window = 10      # 10 minuten
    count_threshold = 1         # minimaal 1 bericht in 10m
    recovery_time = 70          # 70 minuten voor volledig herstel

    gc_threshold = 10           # 10 minuten na gepland vertrek wissen
    gc_threshold_static = 0     # injecties: 0 minuten na gepland vertrek wissen
    gc_threshold_departed = 120 # ritten 120 minuten na vertrek wissen

    keep_departures = False     # debugoptie

    """
    Initialiseer GC thread
    Paremeters:
    - event: threading.Event() object
    - configuration: config dict, bevat optioneel een key 'gc' met optioneel
      waarden 'count_time_window', 'count_threshold', 'recovery_time', 'gc_threshold'
    """
    def __init__(self, event, configuration, keep_departures):
        threading.Thread.__init__(self, name='GarbageThread')
        self.logger = logging.getLogger(__name__)

        # Initialiseer downtime detectie queue
        self.msg_count_queue = deque()

        if 'downtime_detection' in configuration:
            if 'count_time_window' in configuration['downtime_detection']:
                self.count_time_window = int(configuration['downtime_detection']['count_time_window'])
            if 'count_threshold' in configuration['downtime_detection']:
                self.count_threshold = int(configuration['downtime_detection']['count_threshold'])
            if 'recovery_time' in configuration['downtime_detection']:
                self.recovery_time = int(configuration['downtime_detection']['recovery_time'])
        if 'garbage_collection' in configuration:
            if 'gc_threshold' in configuration['garbage_collection']:
                self.gc_threshold = int(configuration['garbage_collection']['gc_threshold'])
            if 'gc_threshold_static' in configuration['garbage_collection']:
                self.gc_threshold_static = int(configuration['garbage_collection']['gc_threshold_static'])
            if 'gc_threshold_departed' in configuration['garbage_collection']:
                self.gc_threshold_departed = int(configuration['garbage_collection']['gc_threshold_departed'])

        self.logger.info("GC thread geinitialiseerd")
        self.logger.info("Configuratie downtimedetectie: window: %sm, threshold: >=%s bericht/min, recovery time: %sm",
                         self.count_time_window,
                         self.count_threshold,
                         self.recovery_time)
        self.logger.info("Configuratie garbage collection: threshold: %sm, threshold statisch: %sm, threshold vertrokken: %sm",
                         self.gc_threshold,
                         self.gc_threshold_static,
                         self.gc_threshold_departed)
        self.stopped = event
        self.keep_departures = keep_departures

    def run(self):
        self.logger.debug("Initiele garbage collecting")
        self.garbage_collect()

        # Loop over garbage collecting iedere 1m:
        while not self.stopped.wait(60):
            try:
                self.logger.debug("Periodieke garbage collecting")
                self.garbage_collect()

                self.logger.info(
                    "Statistieken: station_store=%s, trein_store=%s, status=%s",
                    len(station_store),
                    len(trein_store),
                    system_status['status'])

                # Voeg nieuwe meting toe aan self.msg_count_queue
                total_msg_now = counters['msg']
                self.msg_count_queue.append(total_msg_now)

                # Controleer aantal meetpunten:
                if len(self.msg_count_queue) >= self.count_time_window:
                    # Bereken aantal ontvangen berichten:
                    total_msg_ago = self.msg_count_queue.popleft()
                    msg_received = total_msg_now - total_msg_ago

                    # Log aantal ontvangen berichten binnen tijdwindow:
                    self.logger.info('Ontvangen berichten (%sm window): %s (%.2f/m)',
                        self.count_time_window,
                        msg_received,
                        (msg_received / self.count_time_window))

                    # Bepaal eventuele downtime:
                    if msg_received < self.count_threshold:
                        self.logger.warning('Downtime gedetecteerd, %s berichten ontvangen (%sm window)',
                            msg_received, self.count_time_window)

                        # Registreer downtime status, en eventueel tijdstip van downtime
                        # (indien nog niet bekend)
                        system_status['status'] = 'DOWN'
                        if system_status['down_since'] == None:
                            # Downtime start nu
                            system_status['down_since'] = datetime.now()
                            system_status['recovering_since'] = None

                    else:
                        self.logger.debug('Geen downtime gedetecteerd')

                        # Controleer status voor juiste actie:
                        if system_status['status'] == 'UNKNOWN' or \
                            system_status['status'] == 'DOWN':
                            # Systeem was down of past gestart. Nu komt betrouwbaar
                            # data binnen, zet status naar RECOVERING
                            self.logger.warning('Systeem is RECOVERING na downtime (gestart om %s)',
                                system_status['down_since'])
                            system_status['status'] = 'RECOVERING'
                            system_status['recovering_since'] = datetime.now()

                        elif system_status['status'] == 'RECOVERING':
                            # Systeem is aan het recoveren na downtime. Indien recovery-
                            # tijd voorbij is kan systeem weer naar UP

                            # Controleer recovery tijd:
                            recover_threshold_time = system_status['recovering_since'] + \
                                timedelta(minutes = self.recovery_time)

                            # Ook recovery tijd voorbij, systeemstatus is OK:
                            if datetime.now() >= recover_threshold_time:
                                system_status['status'] = 'UP'
                                self.logger.warning('Systeem weer UP na downtime (%s t/m %s) en recovery. Duur downtime %s',
                                    system_status['down_since'], system_status['recovering_since'],
                                    (system_status['recovering_since'] - system_status['down_since']))
                                system_status['down_since'] = None
                                system_status['recovering_since'] = None

                else:
                    self.logger.debug('Onvoldoende data voor downtime-detectie')

                    # Stel downtime status in op UNKOWN en behandel verder als normale
                    # downtime (log starttijd, etc.)
                    system_status['status'] = 'UNKNOWN'
                    system_status['recovering_since'] = None
                    if system_status['down_since'] is None:
                        system_status['down_since'] = datetime.now()

            except Exception:
                self.logger.error('Fout in GC thread', exc_info=True)

    def garbage_collect(self):
        """
        Garbage collecting.
        Ruimt alle treinen op welke nog niet vertrokken zijn, maar welke
        al wel 10 minuten weg hadden moeten zijn (volgens actuele vertrektijd)
        """

        global station_store, trein_store, counters

        # Bereken threshold:
        threshold = datetime.now(pytz.utc) - timedelta(minutes=self.gc_threshold)
        threshold_statisch = datetime.now(pytz.utc) - timedelta(minutes=self.gc_threshold_static)
        threshold_departed = datetime.now(pytz.utc) - timedelta(minutes=self.gc_threshold_departed)

        # Performance controle; start:
        start = datetime.now()
        verwerkte_items = 0

        # Check alle treinen in station_store:
        for station in station_store:
            try:
                for trein_rit, trein in station_store[station].items():
                    if trein.is_vertrokken():
                        if trein.vertrokken_timestamp is None:
                            # Timestamp ontbreekt, voeg alsnog toe:
                            trein.markeer_vertrokken()
                        else:
                            # Controleer of threshold_departed overschreden is
                            try:
                                if trein.vertrokken_timestamp < threshold_departed and self.keep_departures is False:
                                    del(station_store[station][trein_rit])
                            except KeyError:
                                self.logger.debug("GC: %s/%s al verwijderd", trein_rit, station)
                    else:
                        # Trein is nog niet vertrokken, controleer threshold om rit
                        # als vertrokken te markeren:
                        if (trein.statisch == False and trein.vertrek_actueel < threshold) \
                        or (trein.statisch == True and trein.vertrek_actueel < threshold_statisch):
                            try:
                                with locks['station']:
                                    station_store[station][trein_rit].markeer_vertrokken()

                                verwerkte_items += 1

                                if trein.is_opgeheven():
                                    # Voor opgeheven treinen komt geen wisbericht,
                                    # daarom is het te verwachten dat deze GC'd worden
                                    # Log alleen debug melding
                                    self.logger.debug('GC [SS] %s/%s gemarkeerd als vertrokken (opgeheven)' % (trein_rit, station))
                                elif trein.statisch == True:
                                    self.logger.debug('GC [SS] %s/%s gemarkeerd als vertrokken (statisch)' % (trein_rit, station))
                                else:
                                    # Waarschuwing indien trein niet opgeheven, maar
                                    # wel 10-minuten window overschreden:
                                    self.logger.warn('GC [SS] %s/%s gemarkeerd als vertrokken (geen wisbericht ontvangen)' % (trein_rit, station))

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
                    if trein.is_vertrokken():
                        if trein.vertrokken_timestamp is None:
                            # Timestamp ontbreekt, voeg alsnog toe:
                            trein.markeer_vertrokken()
                            self.logger.warning("GC: trein %s/%s vertrokken maar timestamp leeg", trein_rit, station)
                        else:
                            # Controleer of threshold_departed overschreden is
                            try:
                                if trein.vertrokken_timestamp < threshold_departed and self.keep_departures is False:
                                    del(trein_store[trein_rit][station])
                                    self.logger.debug("GC: TS, trein %s/%s verwijderd", trein_rit, station)
                            except KeyError:
                                self.logger.debug("GC: %s/%s al verwijderd", trein_rit, station)
                    else:
                        # Trein is nog niet vertrokken, controleer threshold om rit
                        # als vertrokken te markeren:
                        if (trein.statisch == False and trein.vertrek_actueel < threshold) \
                        or (trein.statisch == True and trein.vertrek_actueel < threshold_statisch):
                            # Geen trein verwerken die al als vertrokken is gemarkeerd:
                            try:
                                with locks['trein']:
                                    trein_store[trein_rit][station].markeer_vertrokken()

                                verwerkte_items += 1

                                if trein.is_opgeheven():
                                    # Voor opgeheven treinen komt geen wisbericht,
                                    # daarom is het te verwachten dat deze GC'd worden
                                    # Log alleen debug melding
                                    self.logger.debug('GC [TS] %s/%s gemarkeerd als vertrokken (opgeheven)' % (trein_rit, station))
                                elif trein.statisch == True:
                                    self.logger.debug('GC [TS] %s/%s gemarkeerd als vertrokken (statisch)' % (trein_rit, station))
                                else:
                                    # Waarschuwing indien trein niet opgeheven, maar
                                    # wel 10-minuten window overschreden:
                                    self.logger.warn('GC [TS] %s/%s gemarkeerd als vertrokken (geen wisbericht ontvangen)' % (trein_rit, station))

                                    counters['gc_trein'] = counters['gc_trein'] + 1
                            except KeyError:
                                self.logger.debug('GC [TS] Al verwijderd %s/%s', trein_rit, station)
            except KeyError:
                self.logger.debug('GC [TS] Al verwijderd %s', trein_rit)

            # Verwijder treinen uit trein_store dict
            # indien geen informatie meer:
            if trein_rit in trein_store and len(trein_store[trein_rit]) == 0:
                del(trein_store[trein_rit])

        # Bereken duur voor GC en duur per item
        if verwerkte_items > 0:
            duur = datetime.now() - start
            self.logger.debug("GC [TS] * %s items verwerkt in %s (%s per verwerking)", verwerkte_items, duur, (duur / verwerkte_items))

        # Trigger Python GC na deze opruimronde:
        gc.collect()


        return


# Injector thread:
class InjectorThread(threading.Thread):
    """
    Thread die verantwoordelijk is voor verwerken van DVS injecties
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
                trein_dict = client_socket.recv_json()
                
                self.logger.debug("Nieuwe injectie: %s", trein_dict)
                counters['injecties'] += 1

                # Converteer ontvangen dict naar 
                trein = infoplus_dvs.parse_trein_dict(trein_dict, True)
                rit_id = trein.rit_id

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

                # Stuur response naar injector
                client_socket.send_json({'result': True})

            except Exception as e:
                self.logger.exception("Fout tijdens verwerken injectie: %s", e)
                client_socket.send_json({'result': False, 'error': str(e)})

if __name__ == "__main__":
    main()
