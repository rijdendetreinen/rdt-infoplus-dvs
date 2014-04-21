#!/usr/bin/env python2

"""
Script om Nagios controle uit te voeren op DVS systeemstatus.
"""

import zmq
import argparse
import pprint
import sys
import time

def main():
    """
    Main functie
    """

    # Initialiseer argparse
    parser = argparse.ArgumentParser(
        description='Nagios controletool voor DVS systeemstatus')

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
    client.send('status/status')
    
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)
    
    if poller.poll(server_timeout * 1000):
        system_status = client.recv_pyobj()

        if system_status == "UP":
            print "OK - No downtime detected"
            sys.exit(0)
        elif system_status == "RECOVERING":
            print "WARNING - Recovering from downtime"
            sys.exit(1)
        elif system_status == "DOWN":
            print "CRITICAL - Downtime detected, not recovering"
            sys.exit(2)
        elif system_status == "UNKNOWN":
            print "CRITICAL - Status UNKNOWN, system is probably starting up"
            sys.exit(2)
        else:
            print "UKNOWN - Did not receive useful answer from DVS server"
            sys.exit(3)

    else:
        print "CRITICAL - Timeout, server did not respond within %ss" % server_timeout
        sys.exit(2)

if __name__ == "__main__":
    main()
