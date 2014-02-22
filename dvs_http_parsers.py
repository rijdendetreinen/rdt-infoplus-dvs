"""
Module om InfoPlus_DVS objecten naar JSON te vertalen, ten behoeve
van de DVS HTTP interface.
"""

from datetime import timedelta


def trein_to_dict(trein, taal, tijd_nu, materieel=False, stopstations=False):
    """
    Vertaal een InfoPlus_DVS Trein object naar een dict,
    geschikt voor een JSON output.
    Met de parameter materieel wordt de materieelcompositie teruggegeven,
    met de parameter stopstations alle stops per treinvleugel.
    """

    trein_dict = { }

    # Basis treininformatie
    trein_dict['treinNr'] = trein.treinnr
    trein_dict['vertrek'] = trein.lokaal_vertrek().isoformat()
    trein_dict['bestemming'] = '/'.join(bestemming.lange_naam
        for bestemming in trein.eindbestemming_actueel)
    trein_dict['soort'] = trein.soort
    trein_dict['soortAfk'] = trein.soort_code
    trein_dict['vertraging'] = round(trein.vertraging.seconds / 60)
    trein_dict['spoor'] = '/'.join(str(spoor)
        for spoor in trein.vertrekspoor_actueel)

    if '/'.join(str(spoor) for spoor in trein.vertrekspoor) \
        != '/'.join(str(spoor) for spoor in trein.vertrekspoor_actueel):
        trein_dict['sprWijziging'] = True
    else:
        trein_dict['sprWijziging'] = False

    trein_dict['opmerkingen'] = trein.wijzigingen_str(taal, True, trein)

    if trein.treinnaam != None:
        trein_dict['opmerkingen'].append(trein.treinnaam)

    if trein.statisch == True:
        if taal == 'en':
            trein_dict['opmerkingen'].append("No real-time information")
        else:
            trein_dict['opmerkingen'].append("Geen actuele informatie")

    trein_dict['tips'] = trein.tips(taal)
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
        if trein.vertrek + timedelta(minutes = 2) < tijd_nu:
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

    # Treinvleugels:
    trein_dict['vleugels'] = []
    for vleugel in trein.vleugels:
        vleugel_dict = {
            'bestemming': vleugel.eindbestemming_actueel.lange_naam }

        if materieel == True:
            vleugel_dict['mat'] = [
                (mat.treintype(), mat.eindbestemming_actueel.middel_naam)
                for mat in vleugel.materieel]

        if stopstations == True:
            vleugel_dict['stopstations'] = \
                stopstations_to_list(vleugel.stopstations_actueel)

        trein_dict['vleugels'].append(vleugel_dict)

    return trein_dict

def stopstations_to_list(stations):
    """
    Vertaal de stopstations van een trein naar een list van
    stopstations, geschikt om als JSON result terug te geven.
    """

    stations_list = []

    for station in stations:
        stations_list.append(
            {'code': station.code, 'naam': station.lange_naam})

    return stations_list
