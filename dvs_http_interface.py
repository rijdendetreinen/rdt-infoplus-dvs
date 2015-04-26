"""
Module om HTTP requests te vertalen naar de DVS daemon.
Deze module maakt het mogelijk om informatie per station of per trein
op te vragen. Iedere request geeft een JSON response terug.
"""

import zmq
from datetime import datetime
import pytz
import bottle
import logging
from bottle import response

import dvs_http_parsers

SERVER_TIMEOUT = 4
config = {}


@bottle.route('/station/<station>')
@bottle.route('/station/<station>/<taal>')
def index(station, taal='nl'):
    try:
        tijd_nu = datetime.now(pytz.utc)

        # Maak verbinding
        context = zmq.Context()
        client = context.socket(zmq.REQ)
        client.connect(config['dvs']['daemon'])
        client.setsockopt(zmq.LINGER, 0)

        # Stuur opdracht:
        client.send('station/%s' % station)

        # Ontvang response:
        poller = zmq.Poller()
        poller.register(client, zmq.POLLIN)

        if poller.poll(SERVER_TIMEOUT * 1000): # 10s timeout in milliseconds
            data = client.recv_pyobj()
            client.close()
            client.close()
            context.term()
        else:
            client.close()
            context.term()
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': 'DVS server timeout' }

        if 'data' in data:
            # Nieuw formaat met statusdata:
            treinen = data['data']
            status = data['status']['status']
        else:
            # Oude formaat:
            treinen = data
            status = None

        # Lees trein array uit:
        if treinen != None:
            # Bepaal sortering adhv GET-parameter sorteer=
            if bottle.request.query.get('sorteer') == 'actueel':
                # Sorteer op geplande vertrektijd
                treinen_sorted = sorted(treinen,
                    key=lambda trein: treinen[trein].vertrek_actueel)
            elif bottle.request.query.get('sorteer') == 'vertraging':
                # Sorteer op vertraging (hoog naar laag)
                treinen_sorted = sorted(treinen,
                    key=lambda trein: treinen[trein].vertraging)[::-1]
            else:
                # (Standaard) Sorteer op gepland vertrek
                treinen_sorted = sorted(treinen,
                    key=lambda trein: treinen[trein].vertrek)

            if bottle.request.query.get('verbose') == 'true':
                verbose = True
            else:
                verbose = False

            vertrektijden = []

            for trein_nr in treinen_sorted:
                trein = treinen[trein_nr]

                trein_dict = dvs_http_parsers.trein_to_dict(trein, taal, tijd_nu, materieel=verbose)

                if trein_dict != None:
                    vertrektijden.append(trein_dict)

            return { 'result': 'OK', 'system_status': status, 'vertrektijden': vertrektijden }
        else:
            return { 'result': 'OK', 'system_status': status, 'vertrektijden': [] }

        client.close()
        context.term()
    except Exception as e:
        client.close()
        context.term()
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e) }


@bottle.route('/trein/<trein>/<station>')
@bottle.route('/trein/<trein>/<station>/<taal>')
def index(trein, station, taal='nl'):
    try:
        tijd_nu = datetime.now(pytz.utc)

        # Maak verbinding
        context = zmq.Context()
        client = context.socket(zmq.REQ)
        client.connect(config['dvs']['daemon'])
        client.setsockopt(zmq.LINGER, 0)

        # Stuur opdracht: haal alle informatie op voor dit treinnummer
        client.send('trein/%s' % trein)

        # Ontvang response:
        poller = zmq.Poller()
        poller.register(client, zmq.POLLIN)

        if poller.poll(SERVER_TIMEOUT * 1000): # 10s timeout in milliseconds
            data = client.recv_pyobj()
            client.close()
            client.close()
            context.term()
        else:
            client.close()
            context.term()
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': 'DVS server timeout' }

        if 'data' in data:
            # Nieuw formaat met statusdata:
            vertrekken = data['data']
            status = data['status']['status']
        else:
            # Oude formaat:
            vertrekken = data
            status = None

        # Lees trein array uit:
        if vertrekken != None and station.upper() in vertrekken:
            trein_info = vertrekken[station.upper()]

            # Parse basis informatie:
            trein_dict = dvs_http_parsers.trein_to_dict(trein_info,
                taal, tijd_nu, materieel=True, stopstations=True)

            return { 'result': 'OK', 'system_status': status, 'trein': trein_dict }
        else:
            return { 'result': 'ERR', 'system_status': status, 'status': 'NOTFOUND' }

        client.close()
        context.term()
    except Exception as e:
        client.close()
        context.term()
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e) }

@bottle.route('/status')
def index():
    try:
        # Maak verbinding
        context = zmq.Context()
        client = context.socket(zmq.REQ)
        client.connect(config['dvs']['daemon'])
        client.setsockopt(zmq.LINGER, 0)

        # Stuur opdracht:
        client.send('status')

        # Ontvang response:
        poller = zmq.Poller()
        poller.register(client, zmq.POLLIN)

        if poller.poll(SERVER_TIMEOUT * 1000): # 10s timeout in milliseconds
            data = client.recv_pyobj()
            client.close()
            client.close()
            context.term()
        else:
            client.close()
            context.term()
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': 'DVS server timeout' }

        if data['down_since'] != None:
            data['down_since'] = str(data['down_since'])

        if data['recovering_since'] != None:
            data['recovering_since'] = str(data['recovering_since'])

        return { 'result': 'OK', 'data': data }
    except Exception as e:
        client.close()
        context.term()
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e) }
