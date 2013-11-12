import sys
import zmq
from gzip import GzipFile
from cStringIO import StringIO
from datetime import datetime

import pprint

import infoplus_dvs

# Maak output in utf-8 mogelijk in Python 2.x:
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# Socket to talk to server
context = zmq.Context()
socket = context.socket(zmq.SUB)

print "Collecting updates from DVS server..."
socket.connect ("tcp://post.ndovloket.nl:7660")
#socket.connect ("tcp://46.19.34.170:8100")
socket.setsockopt(zmq.SUBSCRIBE, '')

poller = zmq.Poller()
poller.register(socket, zmq.POLLIN)

starttime = datetime.now()
msgNumber = 0

# Datastores:
stationStore = { }
treinStore = { }


#socks = dict(poller.poll())
#print socks

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
			
			# Maak item in stationStore indien niet aanwezig:
			if ritStationCode not in stationStore:
				stationStore[ritStationCode] = {}

			# Maak item in treinStore indien niet aanwezig
			if trein.treinNr not in treinStore:
				treinStore[trein.treinNr] = {}
			
			if trein.status == '5':
				# Trein vertrokken
				print datetime.now().strftime("%H:%M:%S"), ' -->> trein %6s vertrokken van  %s' % (trein.treinNr, ritStationCode)

				# Verwijder uit stationStore
				if trein.treinNr in stationStore[ritStationCode]:
					del(stationStore[ritStationCode][trein.treinNr])

				# Verwijder uit treinStore
				if ritStationCode in treinStore[trein.treinNr]:
					del(treinStore[trein.treinNr][ritStationCode])
					if len(treinStore[trein.treinNr]) == 0:
						del(treinStore[trein.treinNr])
			else:
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

		# Statistics update every 100 messages:
		if msgNumber % 100 == 0:
			print "** (i) Statistieken **"
			print "   Station store: %s stations" % len(stationStore)
			print "   Trein store: %s treinen" % len(treinStore)
			print "   Messages verwerkt: %s" % msgnum
except KeyboardInterrupt:
	print "Exiting..."

	socket.close()
	context.term()

	print "Station store:"
	pprint.pprint(stationStore)

	print "Processed %s messages" % msgNumber