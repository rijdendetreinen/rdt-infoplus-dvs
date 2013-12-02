"""
Module om InfoPlus_DVS objecten naar JSON te vertalen, ten behoeve
van de DVS HTTP interface.
"""

from datetime import timedelta


def trein_to_dict(trein, taal, tijd_nu):
    """
    Vertaal een InfoPlus_DVS Trein object naar een dict,
    geschokt voor een JSON output.
    """

    trein_dict = { }

    # Basis treininformatie
    trein_dict['treinNr'] = trein.treinNr
    trein_dict['vertrek'] = trein.lokaal_vertrek().isoformat()
    trein_dict['bestemming'] = '/'.join(bestemming.lange_naam
        for bestemming in trein.eindbestemmingActueel)
    trein_dict['soort'] = trein.soort
    trein_dict['soortAfk'] = trein.soortCode
    trein_dict['vertraging'] = round(trein.vertraging.seconds / 60)
    trein_dict['spoor'] = '/'.join(str(spoor)
        for spoor in trein.vertrekSpoorActueel)

    if '/'.join(str(spoor) for spoor in trein.vertrekSpoor) \
        != '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel):
        trein_dict['sprWijziging'] = True
    else:
        trein_dict['sprWijziging'] = False

    trein_dict['opmerkingen'] = trein.wijzigingen_str(taal, True, trein)
    trein_dict['tips'] = trein.tips(taal)
    trein_dict['opgeheven'] = False
    trein_dict['status'] = trein.status

    # Trein opgeheven: wis spoor, vertraging etc.
    if trein.is_opgeheven():
        trein_dict['opgeheven'] = True
        trein_dict['spoor'] = None
        trein_dict['vertraging'] = 0

        # Toon geplande eindbestemming bij opgeheven trein:
        trein_dict['bestemming'] = '/'.join(bestemming.lange_naam
            for bestemming in trein.eindbestemming)

        # Controleer of vertrektijd meer dan 2 min geleden is:
        if trein.vertrekActueel + timedelta(minutes = 2) < tijd_nu:
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
        verkorte_route = trein.verkorteRoute
    else:
        verkorte_route = trein.verkorteRouteActueel

    if verkorte_route == None or len(verkorte_route) == 0:
        trein_dict['via'] = None
    else:
        trein_dict['via'] = ', '.join(
            via.middel_naam for via in verkorte_route)

    # Treinvleugels:
    trein_dict['vleugels'] = []
    for vleugel in trein.vleugels:
        vleugel_dict = {
            'bestemming': vleugel.eindbestemmingActueel.lange_naam }
        vleugel_dict['mat'] = [
            (mat.treintype(), mat.eindbestemmingActueel.middel_naam)
            for mat in vleugel.materieel]

        trein_dict['vleugels'].append(vleugel_dict)

    return trein_dict