#!/usr/bin/env python2

"""
Debug script welke rechtstreeks opdrachten naar DVS stuurt.
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
        description='DVS test tool. Stuur opdracht naar DVS daemon')

    parser.add_argument('-l', '--lokaal', dest='lokaal',
        action='store_true', help='Test met lokale server 127.0.0.1:8140')
    parser.add_argument('-q', '--quiet', dest='quiet',
        action='store_true', help='Verberg meegegeven opdracht')
    parser.add_argument('OPDRACHT', nargs='?',
        action='store', help='opdracht naar DVS server', default='store/trein')

    args = parser.parse_args()

    if args.lokaal == True:
        dvs_client_server = "tcp://127.0.0.1:8140"
    else:
        dvs_client_server = "tcp://46.19.34.170:8120"
        dvs_client_server = "tcp://127.0.0.1:8140"

    opdracht = args.OPDRACHT

    if args.quiet == False:
        print "Opdracht naar DVS: %s" % opdracht
        print "--------------------------------"
        print

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)

    # Stuur opdracht:

    trein = {}

    trein['rit_id'] = 412345
    trein['rit_station'] = 'RTD'
    trein['vertrek'] = datetime.now(pytz.utc) + timedelta(minutes=30)
    trein['bestemming_naam'] = 'Den HaagGGG Laan van NOI'
    trein['bestemming_code'] = 'LAA'
    trein['soort_code'] = 'SPC'
    trein['soort'] = 'Sprintercity'
    trein['spoor'] = '4a'
    trein['vervoerder_code'] = 'GW'
    trein['vervoerder_naam'] = 'GeertWays'
    trein['treinnr'] = 12345
    trein['variant'] = None

    client.send_pyobj(trein)
    result = client.recv_pyobj()

    pretty = pprint.PrettyPrinter(indent=4)

    pretty.pprint(result)

if __name__ == "__main__":
    main()
