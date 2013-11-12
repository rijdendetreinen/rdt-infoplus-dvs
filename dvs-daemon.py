import sys
import zmq
from gzip import GzipFile
from cStringIO import StringIO
import pytz
from datetime import datetime, timedelta
import cPickle as pickle
import argparse
import pprint

import infoplus_dvs

# Maak output in utf-8 mogelijk in Python 2.x:
import sys
reload(sys)
sys.setdefaultencoding("utf-8")


# Initialiseer argparse
parser = argparse.ArgumentParser(description='RDT InfoPlus DVS daemon')

#parser.add_argument('-c', dest='configfile', action='store', help='Configuration file (defaults to %s)' % defaultConfig)
parser.add_argument('-ls', '--laad-stations', dest='laadStations', action='store_true', help='Laad stationstore')
parser.add_argument('-lt', '--laad-treinen', dest='laadTreinen', action='store_true', help='Laad treinstore')

args = parser.parse_args()

# Datastores:
stationStore = { }
treinStore = { }
lastGC = None

def garbage_collect():
	"""
	Garbage collecting.
	Ruimt alle treinen op welke nog niet vertrokken zijn, maar welke
	al wel 10 minuten weg hadden moeten zijn (volgens actuele vertrektijd)
	"""
	global lastGC

	alles_vertrokken_tijdstip = datetime.now(pytz.utc) - timedelta(minutes=10)

	# Check alle treinen in stationStore:
	for station in stationStore:
		for treinRit, trein in stationStore[station].items():
			if trein.vertrekActueel < alles_vertrokken_tijdstip:
				del(stationStore[station][treinRit])
				print '[GC] Trein %s te %s verwijderd' % (treinRit, station)

	# Check alle treinen in treinStore:
	for treinRit in treinStore:
		for station, trein in treinStore[treinRit].items():
			if trein.vertrekActueel < alles_vertrokken_tijdstip:
				del(treinStore[treinRit][station])
				print '[GC] Trein %s te %s verwijderd' % (treinRit, station)

	lastGC = datetime.now(pytz.utc)
	return


# Laad oude datastores in (indien gespecifeerd):
if args.laadStations == True:
	print "Inladen stationStore..."
	stationStoreFile = open('datastore/station.store', 'rb')
	stationStore = pickle.load(stationStoreFile)
	stationStoreFile.close()

if args.laadTreinen == True:
	print "Inladen treinStore..."
	treinStoreFile = open('datastore/trein.store', 'rb')
	treinStore = pickle.load(treinStoreFile)
	treinStoreFile.close()

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

#socket.connect ("tcp://post.ndovloket.nl:7660")
socket.connect ("tcp://46.19.34.170:8100")
socket.setsockopt(zmq.SUBSCRIBE, '')

poller = zmq.Poller()
poller.register(socket, zmq.POLLIN)

starttime = datetime.now()
msgNumber = 0

print "Initial GC"
garbage_collect()

#socks = dict(poller.poll())
#print socks


print "Collecting updates from DVS server..."

try:
	while True:
		multipart = socket.recv_multipart()
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

		# Statistics update every 500 messages:
		if msgNumber % 500 == 0:
			print "** (i) Statistieken **"
			print "   Station store: %s stations" % len(stationStore)
			print "   Trein store: %s treinen" % len(treinStore)
			print "   Messages verwerkt: %s" % msgNumber

		# Check elke 150 berichten op laatste GC tijd:
		if msgNumber % 50 == 0:
			if msgNumber % 1000 == 0 or lastGC == None or lastGC < (datetime.now(pytz.utc) - timedelta(minutes=5)):
				print "Garbage collecting..."
				garbage_collect()

except KeyboardInterrupt:
	print "Exiting..."

	socket.close()
	context.term()

	print "Saving station store..."
	pickle.dump(stationStore, open('datadump/station.store', 'wb'), -1)

	print "Saving trein store..."
	pickle.dump(treinStore, open('datadump/trein.store', 'wb'), -1)

	print "Processed %s messages since %s" % (msgNumber, starttime)
