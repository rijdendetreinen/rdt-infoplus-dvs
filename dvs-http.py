#!/usr/bin/env python

"""
Testtool om een lokale HTTP server te starten die verbinding maakt
met dvs-daemon. Niet geschikt voor productie! Gebruik daar WSGI voor.
"""

import bottle
import argparse
import dvs_http_interface
import logging

# Initialiseer argparse
parser = argparse.ArgumentParser(description='DVS HTTP interface test tool')

parser.add_argument('-s', '--server', action='store', default='127.0.0.1', help='DVS server (standaard 127.0.0.1)')
parser.add_argument('-p', '--port', action='store', default='8120', help='DVS poort (standaard 8120)')

args = parser.parse_args()
dvs_http_interface.dvs_client_server = "tcp://%s:%s" % (args.server, args.port)

# Stel logger in:
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.info("Server: %s", dvs_http_interface.dvs_client_server)

bottle.debug(True)
bottle.run(host='localhost', port=8080, reloader=True)