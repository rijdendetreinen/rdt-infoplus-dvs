import sys
import zmq
from gzip import GzipFile
from cStringIO import StringIO
from datetime import datetime

import traceback
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
socket.setsockopt(zmq.SUBSCRIBE, '')

poller = zmq.Poller()
poller.register(socket, zmq.POLLIN)

starttime = datetime.now()
msgNumber = 0

#socks = dict(poller.poll())
#print socks

errorfile = open('dvs-error.log', 'w')

while True:
	multipart = socket.recv_multipart()
	address = multipart[0]
	content = GzipFile('','r',0,StringIO(''.join(multipart[1:]))).read()

	# Parse trein xml:
	try:
		trein = infoplus_dvs.parse_trein(content)
		print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "## %9s ## " % msgNumber, trein

		if trein.ritStationCode in ['RTD', 'UT', 'ASDZ', 'ASD'] or trein.treinNr in ['1927', '1929', '1941', '1743', '36790', '21459', '1409', '21463', '1413', '5710', '919', '9315', '9322', '1218']:
			# Save event:
			filename = '/home/geert/ndovtest/treinlog/%s-%s_%s.xml' % (trein.treinNr, trein.ritStationCode, datetime.now().strftime("%Y%m%d-%H%M%S"))
			logfile = open(filename, 'w')
			logfile.write(content)
			logfile.close()
	except Exception as e:
		print "!!!!!! ERROR! !!!!! %s" % e

		exc_type, exc_value, exc_traceback = sys.exc_info()
		print "*** print_tb:"
		traceback.print_tb(exc_traceback, limit=1)
		traceback.print_tb(exc_traceback, limit=1, file=errorfile)
		print "*** print_exception:"
		traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=errorfile)
		
	msgNumber = msgNumber + 1

errorfile.close()

socket.close()
context.term()
