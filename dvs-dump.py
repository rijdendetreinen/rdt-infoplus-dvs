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

    parser.add_argument('-q', '--quiet', dest='quiet',
        action='store_true', help='verberg debug-informatie')
    parser.add_argument('-s', '--server', action='store', default='127.0.0.1', help='DVS server (standaard 127.0.0.1)')
    parser.add_argument('-p', '--port', action='store', default='8120', help='DVS poort (standaard 8120)')
    parser.add_argument('-t', '--timeout', action='store', default='4', help='timeout in seconden (standaard 4s)')
    parser.add_argument('OPDRACHT', nargs='?',
        action='store', help='opdracht naar DVS server', default='store/trein')

    args = parser.parse_args()

    dvs_client_server = "tcp://%s:%s" % (args.server, args.port)
    server_timeout = int(args.timeout)
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
    client.setsockopt(zmq.LINGER, 0)
    client.send(opdracht)
    
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)
    
    if poller.poll(server_timeout * 1000):
        treinen = client.recv_pyobj()
        pretty = pprint.PrettyPrinter(indent=4)
        pretty.pprint(treinen)
    else:
        print "Timeout: server did not respond within %ss" % server_timeout
        treinen = {}

if __name__ == "__main__":
    main()
