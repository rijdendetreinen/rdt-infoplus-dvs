"""
Module om HTTP requests te vertalen naar de DVS daemon.
Deze module maakt het mogelijk om informatie per station of per trein
op te vragen. Iedere request geeft een JSON response terug.
"""

import zmq
from datetime import datetime
import pytz
import bottle

import dvs_http_parsers

SERVER_TIMEOUT = 4

@bottle.route('/station/<station>')
@bottle.route('/station/<station>/<taal>')
def index(station, taal='nl'):
    tijd_nu = datetime.now(pytz.utc)

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)
    client.setsockopt(zmq.LINGER, 0)

    # Stuur opdracht:
    client.send('station/%s' % station)

    # Ontvang response:
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)

    if poller.poll(SERVER_TIMEOUT * 1000): # 10s timeout in milliseconds
        treinen = client.recv_pyobj()
        client.close()
        client.close()
        context.term()
    else:
        client.close()
        context.term()
        return { 'result': 'ERR', 'status': 'DVS server timeout' }

    # Lees trein array uit:
    if treinen != None:
        # Bepaal sortering adhv GET-parameter sorteer=
        if bottle.request.query.get('sorteer') == 'actueel':
            # Sorteer op geplande vertrektijd
            treinen_sorted = sorted(treinen,
                key=lambda trein: treinen[trein].vertrekActueel)
        elif bottle.request.query.get('sorteer') == 'vertraging':
            # Sorteer op vertraging (hoog naar laag)
            treinen_sorted = sorted(treinen,
                key=lambda trein: treinen[trein].vertraging)[::-1]
        else:
            # (Standaard) Sorteer op gepland vertrek
            treinen_sorted = sorted(treinen,
                key=lambda trein: treinen[trein].vertrek)

        vertrektijden = []

        for trein_nr in treinen_sorted:
            trein = treinen[trein_nr]

            trein_dict = dvs_http_parsers.trein_to_dict(trein, taal, tijd_nu)

            if trein_dict != None:
                vertrektijden.append(trein_dict)

        return { 'result': 'OK', 'vertrektijden': vertrektijden }
    else:
        return { 'result': 'OK', 'vertrektijden': [] }

    client.close()
    context.term()


@bottle.route('/trein/<trein>/<station>')
@bottle.route('/trein/<trein>/<station>/<taal>')
def index(trein, station, taal='nl'):
    tijd_nu = datetime.now(pytz.utc)

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)
    client.setsockopt(zmq.LINGER, 0)

    # Stuur opdracht: haal alle informatie op voor dit treinnummer
    client.send('trein/%s' % trein)

    # Ontvang response:
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)

    if poller.poll(SERVER_TIMEOUT * 1000): # 10s timeout in milliseconds
        vertrekken = client.recv_pyobj()
        client.close()
        client.close()
        context.term()
    else:
        client.close()
        context.term()
        return { 'result': 'ERR', 'status': 'DVS server timeout' }

    # Lees trein array uit:
    if vertrekken != None and station.upper() in vertrekken:
        trein_info = vertrekken[station.upper()]

        # Parse basis informatie:
        trein_dict = dvs_http_parsers.trein_to_dict(trein_info,
            taal, tijd_nu, True)

        return { 'result': 'OK', 'trein': trein_dict }
    else:
        return { 'result': 'ERR', 'msg': 'NOTFOUND' }

    client.close()
    context.term()