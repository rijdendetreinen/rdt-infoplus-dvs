#!/usr/bin/env python2

"""
Debug script om injecties te testen.
"""

import zmq
import argparse
import pprint
import sys
from datetime import datetime, timedelta
import pytz

def main():
    """
    Main functie
    """

    # Maak output in utf-8 mogelijk in Python 2.x:
    reload(sys)
    sys.setdefaultencoding("utf-8")

    # Initialiseer argparse
    parser = argparse.ArgumentParser(
        description='DVS injectie test tool. Injecteer een trein in DVS')

    parser.add_argument('-s', '--server', action='store', default='127.0.0.1', help='DVS server (standaard 127.0.0.1)')
    parser.add_argument('-p', '--port', action='store', default='8120', help='DVS poort (standaard 8120)')
    parser.add_argument('-t', '--timeout', action='store', default='4', help='timeout in seconden (standaard 4s)')

    args = parser.parse_args()

    dvs_client_server = "tcp://%s:%s" % (args.server, args.port)
    server_timeout = int(args.timeout)
    
    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)

    # Stuur opdracht:
    client.setsockopt(zmq.LINGER, 0)
    
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)
    
    trein = {}

    trein['rit_id'] = 'i412345'
    trein['rit_station'] = 'RTD'
    trein['vertrek'] = datetime.now(pytz.utc) + timedelta(minutes=30)
    trein['bestemming_naam'] = 'Den Haag Laan van NOI'
    trein['bestemming_code'] = 'LAA'
    trein['soort_code'] = 'SPC'
    trein['soort'] = 'Sprinter'
    trein['spoor'] = '4a'
    trein['vervoerder_code'] = 'GW'
    trein['vervoerder_naam'] = 'GeWays'
    trein['treinnr'] = 12345
    trein['variant'] = None

    client.send_pyobj(trein)
    if poller.poll(server_timeout * 1000):
        result = client.recv_pyobj()

        pretty = pprint.PrettyPrinter(indent=4)
        pretty.pprint(result)
    else:
        print 'Timeout'

if __name__ == "__main__":
    main()
