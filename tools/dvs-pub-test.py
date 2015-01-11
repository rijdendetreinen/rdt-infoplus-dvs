#!/usr/bin/env python

"""
Test tool om performance van dvs-daemon.py te testen.
Copyright (C) 2015 Geert Wirken

Dit script leest alle berichten in /testdata/dvsmessages.gz in
(ca. 30.000 DVS-berichten) en levert deze in een keer af op
socket tcp://127.0.0.1:12345 (stel dit in als DVS server).
dvs-daemon.py zal enige tijd doen over het verwerken maar moet zonder
problemen alle berichten kunnen ontvangen.

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

import zmq
import time
import gzip
from cStringIO import StringIO

context = zmq.Context()
 
publisher = context.socket(zmq.PUB)
publisher.setsockopt(zmq.SNDHWM, 0)
publisher.bind("tcp://127.0.0.1:12345")

msg_count = 0
messages = []

print "Preparing..."

with gzip.open('../testdata/dvsmessages.gz','rb') as f:
    for line in f:
        out = StringIO()
        with gzip.GzipFile(fileobj=out, mode="w") as f:
            f.write(line)
        message = out.getvalue()
        messages.append(message)

        msg_count = msg_count + 1

start = time.time()
print "Starting to send %s messages" % msg_count

for message in messages:
    publisher.send_multipart(['test', message])

print "Sent %s messages in %.2f sec." % (msg_count, time.time() - start)