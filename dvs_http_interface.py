"""
Module om HTTP requests te vertalen naar de DVS daemon.
Deze module maakt het mogelijk om informatie per station of per trein
op te vragen. Iedere request geeft een JSON response terug.
"""

import zmq
import datetime
import pytz
import bottle
import logging
from bottle import response

import dvs_http_parsers

SERVER_TIMEOUT = 4
config = {}

@bottle.route('/v1/station/<station>')
@bottle.route('/v1/station/<station>/<taal>')
@bottle.route('/v2/station/<station>')
@bottle.route('/v2/station/<station>')
def station_details(station, taal='nl'):
    if bottle.request.query.get('taal') != '':
        taal = bottle.request.query.get('taal')

    try:
        tijd_nu = datetime.datetime.now(pytz.utc)

        # Stuur opdracht:
        data = _send_dvs_command('station/%s' % station)

        if 'data' in data:
            # Nieuw formaat met statusdata:
            treinen = data['data']
            dvs_status = data['status']['status']
        else:
            # Oude formaat:
            treinen = data
            dvs_status = None

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

                if trein_dict != None and not trein.is_vertrokken():
                    vertrektijden.append(trein_dict)

            return {'result': 'OK', 'system_status': dvs_status, 'vertrektijden': vertrektijden}
        else:
            return {'result': 'OK', 'system_status': dvs_status, 'vertrektijden': []}
    except Exception as e:
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e) }

@bottle.route('/v2/trein/<trein>')
@bottle.route('/v2/trein/<trein>/<datum>')
@bottle.route('/v2/trein/<trein>/<datum>/<station>')
def trein_details(trein, datum='vandaag', station=None):
    taal = 'nl'
    if bottle.request.query.get('taal') != '':
        taal = bottle.request.query.get('taal')

    return get_trein_details(trein, datum=datum, station=station, taal=taal)

@bottle.route('/v1/trein/<trein>/<station>')
@bottle.route('/v1/trein/<trein>/<station>/<taal>')
def trein_details_legacy(trein, station, taal='nl'):
    """
    Legacy methode voor opvragen treindetails
    """

    return get_trein_details(trein, station=station, taal=taal)

def get_trein_details(trein, datum='vandaag', station=None, taal='nl'):
    if datum == 'vandaag':
        datum = get_current_servicedate()

    try:
        tijd_nu = datetime.datetime.now(pytz.utc)
        serviceinfo = None

        # Stuur opdracht: haal alle informatie op voor dit treinnummer
        data = _send_dvs_command('trein/%s' % trein)

        if 'data' in data:
            vertrekken = data['data']
            dvs_status = data['status']['status']
        else:
            vertrekken = data
            dvs_status = None

        # Indien geen station opgegeven:
        # Zoek rit in serviceinfo, gebruik eerste station als ritstation.
        if station is None:
            serviceinfo = dvs_http_parsers.retrieve_serviceinfo(trein, datum, config['serviceinfo'])
            if serviceinfo is not None and 'stops' in serviceinfo[0]:
                station = serviceinfo[0]['stops'][0]['station']

        # Lees trein array uit:
        if vertrekken != None and station.upper() in vertrekken:
            trein_info = vertrekken[station.upper()]

            # Parse basisinformatie:
            trein_dict = dvs_http_parsers.trein_to_dict(trein_info,
                taal, tijd_nu, materieel=True, stopstations=True, serviceinfo_config=config['serviceinfo'])

            return {'result': 'OK', 'system_status': dvs_status, 'trein': trein_dict, 'source': 'dvs'}
        else:
            # Probeer trein te zoeken in serviceinfo:
            if serviceinfo is None:
                # Niet opnieuw opvragen indien nog beschikbaar
                serviceinfo = dvs_http_parsers.retrieve_serviceinfo(trein, datum, config['serviceinfo'])
            trein_dict = dvs_http_parsers.serviceinfo_to_dict(serviceinfo, station)

            if trein_dict is not None:
                return {'result': 'OK', 'system_status': dvs_status, 'trein': trein_dict, 'source': 'serviceinfo'}
            else:
                return {'result': 'ERR', 'system_status': dvs_status, 'status': 'NOTFOUND'}

    except Exception as e:
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return { 'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e) }

def get_current_servicedate():
    # TODO: rekening houden met tijdzone, overgang om 4.00 uur 's nachts
    return datetime.date.today().isoformat()

@bottle.route('/v1/status')
@bottle.route('/v2/status')
def status():
    try:
        # Stuur opdracht:
        data = _send_dvs_command('status')

        if data['down_since'] != None:
            data['down_since'] = str(data['down_since'])

        if data['recovering_since'] != None:
            data['recovering_since'] = str(data['recovering_since'])

        return {'result': 'OK', 'data': data}
    except Exception as e:
        try:
            logger = logging.getLogger(__name__)
            logger.exception("ERROR")
        finally:
            response.status = 500
            return {'result': 'ERR', 'system_status': 'UNKOWN', 'status': str(e)}


def _send_dvs_command(command):
    """
    Bereid de ZeroMQ connectie naar de DVS daemon voor
    """

    # Maak verbinding
    context = zmq.Context()
    client = context.socket(zmq.REQ)
    client.connect(config['dvs']['daemon'])
    client.setsockopt(zmq.LINGER, 0)

    # Stuur opdracht:
    client.send(command)

    # Ontvang response:
    poller = zmq.Poller()
    poller.register(client, zmq.POLLIN)

    if poller.poll(SERVER_TIMEOUT * 1000):
        data = client.recv_pyobj()
        client.close()
        context.term()

        return data
    else:
        client.close()
        context.term()

        raise DvsException('DVS Server Timeout')


class DvsException(Exception):
    """
    Exception class voor DVS fouten
    """

    pass
