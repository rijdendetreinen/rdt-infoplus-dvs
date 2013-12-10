#!/usr/bin/env python

"""
Test tool om een lokale HTTP server te starten.
"""

import bottle
import argparse
import dvs_http_interface
import logging

# Initialiseer argparse
parser = argparse.ArgumentParser(description='DVS HTTP interface test tool')

parser.add_argument('-l', '--lokaal', dest='lokaal',
    action='store_true', help='Test met lokale server 127.0.0.1:8120')

args = parser.parse_args()

if args.lokaal == True:
    dvs_http_interface.dvs_client_server = "tcp://127.0.0.1:8120"
else:
    dvs_http_interface.dvs_client_server = "tcp://46.19.34.170:8120"

# Stel logger in:
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.info("Server: %s", dvs_http_interface.dvs_client_server)

bottle.debug(True)
bottle.run(host='localhost', port=8080, reloader=True)