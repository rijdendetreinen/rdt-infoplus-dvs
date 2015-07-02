#!/usr/bin/env python

"""
Testtool om een lokale HTTP server te starten die verbinding maakt
met dvs-daemon. Niet geschikt voor productie! Gebruik daar WSGI voor.
"""

import bottle
import argparse
import logging

import dvs_http_interface
import dvs_util

def main():
    """
    Main loop
    """

    # Initialiseer argparse
    parser = argparse.ArgumentParser(description='DVS HTTP interface test tool')

    parser.add_argument('-c', '--config', dest='configFile',
        default='config/http.yaml', action='store',
        help='HTTP configuratiebestand')

    # Parse config:
    args = parser.parse_args()
    config = dvs_util.load_config(args.configFile)

    # Stel logger in:
    dvs_util.setup_logging(config)

    dvs_http_interface.config = config

    # Start bottle:
    logger = logging.getLogger(__name__)
    logger.info("DVS server: %s", config['dvs']['daemon'])

    bottle.debug(True)
    bottle.run(host='localhost', port=8080, reloader=True)


if __name__ == "__main__":
    main()
