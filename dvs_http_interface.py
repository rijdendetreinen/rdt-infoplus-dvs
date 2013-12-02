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

@bottle.route('/station/<station>')
@bottle.route('/station/<station>/<taal>')
def index(station, taal='nl'):
    tijd_nu = datetime.now(pytz.utc)

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(dvs_client_server)

    # Stuur opdracht:
    client.send('station/%s' % station)
    treinen = client.recv_pyobj()

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

            vertrektijden.append(trein_dict)

        return { 'result': 'OK', 'vertrektijden': vertrektijden }
    else:
        return { 'result': 'OK', 'vertrektijden': [] }

    client.close()
    context.term()
