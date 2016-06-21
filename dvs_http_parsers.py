"""
Module om InfoPlus_DVS objecten naar JSON te vertalen, ten behoeve
van de DVS HTTP interface.
"""

from datetime import timedelta
import urllib2
import socket
import json
import logging

_logger = logging.getLogger(__name__)


def trein_to_dict(trein, taal, tijd_nu, materieel=False, stopstations=False, serviceinfo_config=None, insert_vertrekstation=False):
    """
    Vertaal een InfoPlus_DVS Trein object naar een dict,
    geschikt voor een JSON output.
    Met de parameter materieel wordt de materieelcompositie teruggegeven,
    met de parameter stopstations alle stops per treinvleugel.
    """

    trein_dict = {}

    # Basis treininformatie
    trein_dict['treinNr'] = trein.treinnr
    trein_dict['id'] = trein.rit_id
    trein_dict['vertrek'] = trein.lokaal_vertrek().isoformat()

    # Parse eindbestemming. Indien eindbestemming uit twee delen bestaat
    # (vleugeltrein), check dan of beide eindbestemmingen verschillen:
    if len(trein.eindbestemming_actueel) == 1:
        trein_dict['bestemming'] = trein.eindbestemming_actueel[0].lange_naam
    else:
        if trein.eindbestemming_actueel[0].lange_naam == trein.eindbestemming_actueel[1].lange_naam:
            # Eindbestemmingen gelijk
            trein_dict['bestemming'] = trein.eindbestemming_actueel[0].lange_naam
        else:
            # Verschillende eindbestemmingen:
            trein_dict['bestemming'] = '/'.join(bestemming.lange_naam
                for bestemming in trein.eindbestemming_actueel)

    trein_dict['soort'] = trein.soort
    trein_dict['soortAfk'] = trein.soort_code
    trein_dict['vertraging'] = float(round(float(trein.vertraging) / 60))
    trein_dict['spoor'] = '/'.join(str(spoor)
        for spoor in trein.vertrekspoor_actueel)

    if '/'.join(str(spoor) for spoor in trein.vertrekspoor) \
        != '/'.join(str(spoor) for spoor in trein.vertrekspoor_actueel):
        trein_dict['sprWijziging'] = True
    else:
        trein_dict['sprWijziging'] = False

    trein_dict['opmerkingen'] = trein.wijzigingen_str(taal, True, trein)
    trein_dict['tips'] = trein.tips(taal)

    # Controleer of alle treindelen naar de vleugel-eindbestemming gaan
    afwijkende_eindbestemming = {}
    afwijkende_eindbestemming_nrs = {}

    for vleugel in trein.vleugels:
        for mat in vleugel.materieel:
            if mat.is_loc():
                continue
            if mat.eindbestemming_actueel.code != vleugel.eindbestemming_actueel.code:
                if mat.get_matnummer() != None:
                    if mat.eindbestemming_actueel.lange_naam not in afwijkende_eindbestemming_nrs:
                        afwijkende_eindbestemming_nrs[mat.eindbestemming_actueel.lange_naam] = []
                    afwijkende_eindbestemming_nrs[mat.eindbestemming_actueel.lange_naam].append(mat.get_matnummer())
                else:
                    if mat.eindbestemming_actueel.lange_naam not in afwijkende_eindbestemming:
                        afwijkende_eindbestemming[mat.eindbestemming_actueel.lange_naam] = []

                    if mat.vertrekpositie not in afwijkende_eindbestemming[mat.eindbestemming_actueel.lange_naam]:
                        afwijkende_eindbestemming[mat.eindbestemming_actueel.lange_naam].append(mat.vertrekpositie)

    # Verwerk afwijkende eindbestemming naar opmerking:
    if len(afwijkende_eindbestemming_nrs) > 0:
        for bestemming in afwijkende_eindbestemming_nrs:
            matnummers = ", ".join(afwijkende_eindbestemming_nrs[bestemming])
            if taal == 'en':
                trein_dict['opmerkingen'].append("Coach %s terminates at %s" % (matnummers, bestemming))
            else:
                trein_dict['opmerkingen'].append("Treinstel %s tot %s" % (matnummers, bestemming))

    # Verwerk afwijkende treindelen zonder matnummer naar opmerking:
    if taal == 'en':
        treindelen_strings = {1: 'front', 2: 'middle', 3: 'rear'}
    else:
        treindelen_strings = {1: 'voorste', 2: 'middelste', 3: 'achterste'}

    if len(afwijkende_eindbestemming) > 0:
        for bestemming in afwijkende_eindbestemming:
            treindelen = []
            for vertrekpositie in afwijkende_eindbestemming[bestemming]:
                if vertrekpositie is None:
                    vertrekpositie = 1
                treindelen.append(treindelen_strings[int(vertrekpositie)])

            if taal == 'en':
                treindelen_string = " and ".join(treindelen).capitalize()
                trein_dict['opmerkingen'].append("%s train part terminates at %s" % (treindelen_string, bestemming))
            else:
                treindelen_string = " en ".join(treindelen).capitalize()
                trein_dict['opmerkingen'].append("%s treindeel tot %s" % (treindelen_string, bestemming))

    if trein.statisch == True:
        if taal == 'en':
            trein_dict['opmerkingen'].append("No real-time information")
        else:
            trein_dict['opmerkingen'].append("Geen actuele informatie")

    # Voeg de treinnaam toe aan reistips:
    if trein.treinnaam != None:
        trein_dict['tips'].append(trein.treinnaam_str(taal))

    trein_dict['opgeheven'] = False
    trein_dict['status'] = trein.status
    trein_dict['vervoerder'] = trein.vervoerder

    # Trein opgeheven: wis spoor, vertraging etc.
    if trein.is_opgeheven():
        trein_dict['opgeheven'] = True
        trein_dict['spoor'] = None
        trein_dict['vertraging'] = 0

        # Toon geplande eindbestemming bij opgeheven trein:
        trein_dict['bestemming'] = '/'.join(bestemming.lange_naam
            for bestemming in trein.eindbestemming)

        # Controleer of vertrektijd meer dan 2 min geleden is:
        if trein.vertrek + timedelta(minutes=2) < tijd_nu:
            # Sla deze trein over. We laten opgeheven treinen tot 2 min
            # na vertrek in de feed zitten; vertrektijd van deze trein
            # is meer dan 2 minuten na vertrektijd
            return None

    else:
        # Trein is niet opgeheven

        # Stuur bij een gewijzigde eindbestemming
        # ook de oorspronkelijke eindbestemming mee:
        if trein_dict['bestemming'] != \
            '/'.join(bestemming.lange_naam \
        for bestemming in trein.eindbestemming):
            trein_dict['bestemmingOrigineel'] = '/'. \
                join(bestemming.lange_naam \
                for bestemming in trein.eindbestemming)

    # Verkorte (via)-route
    if trein_dict['opgeheven'] == True:
        verkorte_route = trein.verkorte_route
    else:
        verkorte_route = trein.verkorte_route_actueel

    if verkorte_route == None or len(verkorte_route) == 0:
        trein_dict['via'] = None
    else:
        trein_dict['via'] = ', '.join(
            via.middel_naam for via in verkorte_route)

    insert_vertrekstation_dict = None
    if insert_vertrekstation is True:
        insert_vertrekstation_dict = {
            'code': trein.rit_station.code,
            'naam': trein.rit_station.lange_naam,
            'vertrekspoor': trein_dict['spoor'],
            'sprWijziging': trein_dict['sprWijziging'],
            'vertrek': trein_dict['vertrek'],
            'vertragingVertrek': trein_dict['vertraging'],
            'aankomst': None,
            'vertragingAankomst': 0,
            'aankomstspoor': None
        }

    # Treinvleugels:
    trein_dict['vleugels'] = []
    for vleugel in trein.vleugels:
        vleugel_dict = {
            'bestemming': vleugel.eindbestemming_actueel.lange_naam}

        if materieel == True:
            vleugel_dict['mat'] = [
                (mat.treintype(), mat.eindbestemming_actueel.middel_naam, mat.get_matnummer())
                for mat in vleugel.materieel]

        if stopstations == True:
            vleugel_dict['stopstations'] = stopstations_to_list(
                vleugel.stopstations_actueel, trein.rit_id,
                trein.rit_datum, serviceinfo_config, insert_vertrekstation_dict)

        trein_dict['vleugels'].append(vleugel_dict)

    return trein_dict


def serviceinfo_to_dict(serviceinfo, station, negeer_stops_tm=False):
    """
    Vertaal een serviceinfo dict naar een dictionary zoals
    deze door trein_to_dict wordt teruggegeven
    """

    if serviceinfo is None or station is None:
        return None

    if len(serviceinfo) == 0:
        return None

    service = serviceinfo[0]

    # Check stops
    stop = None
    for check_stop in service['stops']:
        if check_stop['station'].lower() == station.lower():
            stop = check_stop

    if stop is None:
        return None

    bestemming = service['stops'][-1]['station_name']

    trein_dict = {
        'status': 0,
        'opgeheven': service['cancelled'],
        'via': None,
        'bestemming': bestemming,
        'vervoerder': service['company_name'],
        'soort': service['transport_mode_description'],
        'soortAfk': service['transport_mode'],
        'treinNr': service['service_number'],
        'id': service['service_number'],
        'vertrek': None,
        'spoor': None,
        'sprWijziging': False,
        'vertraging': 0,
        'vleugels': [{
            'bestemming': bestemming,
            'mat': [],
            'stopstations': []
        }],
        'opmerkingen': [],
        'tips': []
    }

    if stop['departure_time'] is not None:
        trein_dict['vertrek'] = stop['departure_time']

    if stop['scheduled_departure_platform'] is not None:
        trein_dict['spoor'] = stop['scheduled_departure_platform']

    if stop['departure_delay'] is not None:
        trein_dict['vertraging'] = stop['departure_delay']

    if stop['actual_departure_platform'] is not None and stop['actual_departure_platform'] != stop['scheduled_departure_platform']:
        trein_dict['spoor'] = stop['actual_departure_platform']
        trein_dict['sprWijziging'] = True

    for stop_data in service['stops']:
        stop_dict = {}
        stop_dict = parse_stop_data(stop_data, stop_dict)

        if negeer_stops_tm == False:
            trein_dict['vleugels'][0]['stopstations'].append(stop_dict)
        else:
            if stop_dict['code'].upper() == station.upper():
                negeer_stops_tm = False

    return trein_dict


def stopstations_to_list(stations, treinnr, ritdatum, serviceinfo_config, insert_vertrekstation_dict=None):
    """
    Vertaal de stopstations van een trein naar een list van
    stopstations, geschikt om als JSON result terug te geven.
    """

    stations_list = []

    if insert_vertrekstation_dict is not None:
        stations_list.append(insert_vertrekstation_dict )

    serviceinfo = retrieve_serviceinfo(treinnr, ritdatum, serviceinfo_config)

    destination_code = stations[-1].code.lower()

    for station in stations:
        station_dict = {'code': station.code, 'naam': station.lange_naam}
        
        extra_stop_data = None
        if serviceinfo != None:
            # Zoek halte op in serviceinfo.
            for service in serviceinfo:
                # Zoek alleen in vleugel met zelfde eindbestemming:
                if service['stops'][-1]['station'] == destination_code:
                    for stop in service['stops']:
                        if stop['station'].lower() == station.code.lower():
                            extra_stop_data = stop
                            break

            # Fallback: indien nog geen stop gevonden is, probeer
            # het nogmaals zonder check op eindbestemming vleugel
            if extra_stop_data is None:
                for service in serviceinfo:
                    for stop in service['stops']:
                        if stop['station'].lower() == station.code.lower():
                            extra_stop_data = stop
                            break

            if extra_stop_data != None:
                # Verwerk spoorinformatie:
                station_dict = parse_stop_data(extra_stop_data, station_dict)

        # Voeg station toe aan de list met alle stations
        stations_list.append(station_dict)

    return stations_list


def parse_stop_data(stop_data, station_dict):
    if stop_data is None:
        return station_dict

    # Stel code en naam in (indien nog niet ingesteld):
    if 'naam' not in station_dict:
        station_dict['naam'] = stop_data['station_name']

    if 'code' not in station_dict:
        station_dict['code'] = stop_data['station']

    # Verwerk spoorinformatie:
    station_dict['sprWijziging'] = False
    station_dict['aankomstspoor'] = stop_data['scheduled_arrival_platform']
    station_dict['vertrekspoor'] = stop_data['scheduled_departure_platform']

    if stop_data['actual_arrival_platform'] != None and \
                    stop_data['scheduled_arrival_platform'] != stop_data['actual_arrival_platform']:
        station_dict['aankomstspoor'] = stop_data['actual_arrival_platform']
        station_dict['sprWijziging'] = True

    if stop_data['actual_departure_platform'] != None and \
                    stop_data['scheduled_departure_platform'] != stop_data['actual_departure_platform']:
        station_dict['vertrekspoor'] = stop_data['actual_departure_platform']
        station_dict['sprWijziging'] = True

    # Overige data:
    station_dict['aankomst'] = stop_data['arrival_time']
    station_dict['vertrek'] = stop_data['departure_time']
    station_dict['vertragingAankomst'] = stop_data['arrival_delay']
    station_dict['vertragingVertrek'] = stop_data['departure_delay']

    return station_dict


def retrieve_serviceinfo(treinnr, ritdatum, serviceinfo_config):
    """
    Haal extra serviceinformatie op om de informatie over stops te verrijken
    met bijvoorbeeld aankomsttijd etc.

    Bij fouten, uitgeschakelde serviceinfo configuratie, etc. geeft deze method None.
    In alle andere gevallen wordt de services dict van de rdt-serviceinfo API teruggegeven.
    """

    if serviceinfo_config == None or serviceinfo_config['enabled'] == False:
        return None
    else:
        try:
            trein_url = "%sservice/%s/%s" % (serviceinfo_config['url'], ritdatum, treinnr)
            response = urllib2.urlopen(trein_url, timeout=2)
            data = json.load(response)

            if 'services' in data:
                return data['services']
            else:
                return None
        except ValueError as error:
            _logger.error("Ongeldige JSON voor serviceinfo (datalengte: %s)")
        except urllib2.URLError as error:
            if isinstance(error.reason, socket.timeout):
                _logger.warn("Serviceinfo timeout: %s", error)
            elif error.errno == 101:
                _logger.warn("Netwerkfout: %s", error)
            elif error.code == 404:
                _logger.debug("Service niet gevonden: %s", error)
            else:
                _logger.error("HTTP fout: %s. Geen serviceinfo beschikbaar", error)
        except Exception as error:
            _logger.error("Generieke fout: %s. Geen serviceinfo beschikbaar", error)
            return None
