#!/usr/bin/env python2

"""
Debug script welke rechtstreeks opdrachten naar DVS stuurt.
"""

import zmq
import argparse
import pprint
import sys

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
        action='store_true', help='Test met lokale server 127.0.0.1:8120')
    parser.add_argument('OPDRACHT', nargs='?',
        action='store', help='opdracht naar DVS server', default='store/trein')

    args = parser.parse_args()

    if args.lokaal == True:
        dvs_client_server = "tcp://127.0.0.1:8120"
    else:
        dvs_client_server = "tcp://46.19.34.170:8120"

    opdracht = args.OPDRACHT

    print "Opdracht naar DVS: %s" % opdracht
    print "--------------------------------"
    print

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)

    # Stuur opdracht:
    client.send(opdracht)
    treinen = client.recv_pyobj()

    pretty = pprint.PrettyPrinter(indent=4)

    pretty.pprint(treinen)

if __name__ == "__main__":
    main()
