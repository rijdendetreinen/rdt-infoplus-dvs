import sys
import zmq
from gzip import GzipFile
from cStringIO import StringIO
from datetime import datetime

import infoplus_dvs

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

while True:
	multipart = socket.recv_multipart()
	address = multipart[0]
	content = GzipFile('','r',0,StringIO(''.join(multipart[1:]))).read()

	# Parse trein xml:
	try:
		trein = infoplus_dvs.parse_trein(content)
		print datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trein
		print "#####, msg=%s" % msgNumber
	except Exception as e:
		print "!!!!!! ERROR! !!!!! %s" % e.msg

	msgNumber = msgNumber + 1

socket.close()
context.term()
