import sys
import zmq
from gzip import GzipFile
from cStringIO import StringIO
import pytz
from datetime import datetime, timedelta
import cPickle as pickle
import argparse
import gc

from threading import Thread, Event

import infoplus_dvs

# Maak output in utf-8 mogelijk in Python 2.x:
reload(sys)
sys.setdefaultencoding("utf-8")


# Default config (nog naar losse configfile):
#dvs_server = "tcp://post.ndovloket.nl:7660"
dvs_server = "tcp://46.19.34.170:8100"
dvs_client_bind = "tcp://0.0.0.0:8120"

# Initialiseer argparse
parser = argparse.ArgumentParser(description='RDT InfoPlus DVS daemon')

parser.add_argument('-ls', '--laad-stations', dest='laadStations', action='store_true', help='Laad stationstore')
parser.add_argument('-lt', '--laad-treinen', dest='laadTreinen', action='store_true', help='Laad treinstore')

args = parser.parse_args()

# Datastores:
stationStore = { }
treinStore = { }

def garbage_collect():
    """
    Garbage collecting.
    Ruimt alle treinen op welke nog niet vertrokken zijn, maar welke
    al wel 10 minuten weg hadden moeten zijn (volgens actuele vertrektijd)
    """
    alles_vertrokken_tijdstip = datetime.now(pytz.utc) - timedelta(minutes=10)

    # Check alle treinen in stationStore:
    for station in stationStore:
        for treinRit, trein in stationStore[station].items():
            if trein.vertrekActueel < alles_vertrokken_tijdstip:
                del(stationStore[station][treinRit])
                print '[GC] Trein %s te %s verwijderd' % (treinRit, station)

    # Check alle treinen in treinStore:
    for treinRit in treinStore.keys():
        for station, trein in treinStore[treinRit].items():
            if trein.vertrekActueel < alles_vertrokken_tijdstip:
                del(treinStore[treinRit][station])
                print '[GC] Trein %s te %s verwijderd' % (treinRit, station)

        # Verwijder treinen uit treinStore dict
        # indien geen informatie meer:
        if len(treinStore[treinRit]) == 0:
            del(treinStore[treinRit])

    gc.collect()

    return


# Laad oude datastores in (indien gespecifeerd):
if args.laadStations == True:
    print "Inladen stationStore..."
    stationStoreFile = open('datadump/station.store', 'rb')
    stationStore = pickle.load(stationStoreFile)
    stationStoreFile.close()

if args.laadTreinen == True:
    print "Inladen treinStore..."
    treinStoreFile = open('datadump/trein.store', 'rb')
    treinStore = pickle.load(treinStoreFile)
    treinStoreFile.close()

# Start eigen daemon:
class ClientThread(Thread):
    def __init__ (self):
        Thread.__init__(self)
        print "Initializing read_thread"
    def run(self):
        print "Running read_thread"
        client_socket = context.socket(zmq.REP)
        client_socket.bind(dvs_client_bind)
        while True:
            url = client_socket.recv()
            try:
                arguments = url.split('/')

                if arguments[0] == 'station' and len(arguments) == 2:
                    stationCode = arguments[1].upper()
                    if stationCode in stationStore:
                        client_socket.send_pyobj(stationStore[stationCode])
                    else:
                        client_socket.send_pyobj({})
                elif arguments[0] == 'trein' and len(arguments) == 2:
                    treinNr = arguments[1]
                    if treinNr in treinStore:
                        client_socket.send_pyobj(treinStore[treinNr])
                    else:
                        client_socket.send_pyobj({})
                else:
                    client_socket.send_pyobj(None)
            except Exception as e:
                client_socket.send_pyobj(None)
                print e
        Thread.__init__(self)

# Garbage collection thread:
class GarbageThread(Thread):
    def __init__(self, event):
        Thread.__init__(self)
        print "GC thread initialized"
        self.stopped = event

    def run(self):
        while not self.stopped.wait(60):
            try:
                print "Garbage collecting..."
                garbage_collect()

                print "** (i) Statistieken **"
                print "   Station store: %s stations" % len(stationStore)
                print "   Trein store: %s treinen" % len(treinStore)
            except Exception as e:
                print e

# Socket to talk to server
context = zmq.Context()

# Start een nieuwe thread om client requests uit te lezen
client_thread = ClientThread()
client_thread.start()

server_socket = context.socket(zmq.SUB)
server_socket.connect(dvs_server)
server_socket.setsockopt(zmq.SUBSCRIBE, '')

poller = zmq.Poller()
poller.register(server_socket, zmq.POLLIN)

starttime = datetime.now()
msgNumber = 0

print "Initial GC"
garbage_collect()

# Start nieuwe thread voor garbage collecting:
gc_stopped = Event()
gc_thread = GarbageThread(gc_stopped)
gc_thread.start()

#socks = dict(poller.poll())
#print socks


print "Collecting updates from DVS server..."

try:
    while True:
        multipart = server_socket.recv_multipart()
        address = multipart[0]
        content = GzipFile('','r',0,StringIO(''.join(multipart[1:]))).read()

        # Parse trein xml:
        try:
            trein = infoplus_dvs.parse_trein(content)
            #print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "## %9s ## trst=%s " % (msgNumber, trein.status), trein

            ritStationCode = trein.ritStation.code
            
            if trein.status == '5':
                # Trein vertrokken
                print datetime.now().strftime("%H:%M:%S"), ' -->> trein %6s vertrokken van  %s' % (trein.treinNr, ritStationCode)

                # Verwijder uit stationStore
                if ritStationCode in stationStore and trein.treinNr in stationStore[ritStationCode]:
                    del(stationStore[ritStationCode][trein.treinNr])

                # Verwijder uit treinStore
                if trein.treinNr in treinStore and ritStationCode in treinStore[trein.treinNr]:
                    del(treinStore[trein.treinNr][ritStationCode])
                    if len(treinStore[trein.treinNr]) == 0:
                        del(treinStore[trein.treinNr])
            else:
                # Maak item in treinStore indien niet aanwezig
                if trein.treinNr not in treinStore:
                    treinStore[trein.treinNr] = {}

                # Maak item in stationStore indien niet aanwezig:
                if ritStationCode not in stationStore:
                    stationStore[ritStationCode] = {}

                # Update of insert trein aan station:
                stationStore[ritStationCode][trein.treinNr] = trein
                treinStore[trein.treinNr][ritStationCode] = trein

                if trein.status == '2':
                    print datetime.now().strftime("%H:%M:%S"), ' >>-- trein %6s aangekomen te   %s' % (trein.treinNr, ritStationCode)
                if trein.status == '0':
                    print datetime.now().strftime("%H:%M:%S"), ' ---- trein %6s status onbekend %s' % (trein.treinNr, ritStationCode)

        except Exception as e:
            print "!!!!!! Error: %s" % e
            
        msgNumber = msgNumber + 1


except KeyboardInterrupt:
    print "Exiting..."

    server_socket.close()
    context.term()

    gc_stopped.set()

    print "Saving station store..."
    pickle.dump(stationStore, open('datadump/station.store', 'wb'), -1)

    print "Saving trein store..."
    pickle.dump(treinStore, open('datadump/trein.store', 'wb'), -1)

    print "Processed %s messages since %s" % (msgNumber, starttime)
