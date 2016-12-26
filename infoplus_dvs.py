"""
Module om DVS berichten uit InfoPlus te kunnen verwerken.
"""

import xml.etree.cElementTree as ET
import isodate
import datetime
import pytz
import logging
import re

# Vraag een logger object:
__logger__ = logging.getLogger(__name__)

def parse_trein(data):
    """
    Vertaal een XML-bericht over een trein (uit de DVS feed)
    naar een Trein object.
    """

    # Parse XML:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exception:
        __logger__.error("Kan XML niet parsen: %s", exception)
        raise OngeldigDvsBericht()

    # Zoek belangrijke nodes op:
    product = root.find('{urn:ndov:cdm:trein:reisinformatie:data:4}ReisInformatieProductDVS')
    namespace = "urn:ndov:cdm:trein:reisinformatie:data:4"

    if product is None:
        # Probeer oude namespace (DVS-TIBCO):
        product = root.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisInformatieProductDVS')
        namespace = "urn:ndov:cdm:trein:reisinformatie:data:2"

    vertrekstaat = product.find('{%s}DynamischeVertrekStaat' % namespace)
    trein_node = vertrekstaat.find('{%s}Trein' % namespace)

    # Maak trein object:
    trein = Trein()
    
    # Metadata over rit:
    trein.rit_datum = vertrekstaat.find('{%s}RitDatum' % namespace).text
    trein.rit_station = parse_station(vertrekstaat.find('{%s}RitStation' % namespace), namespace)
    trein.rit_timestamp = isodate.parse_datetime(product.attrib.get('TimeStamp'))
    
    # Treinnummer, soort/formule, etc:
    trein.treinnr = trein_node.find('{%s}TreinNummer' % namespace).text
    trein.rit_id = trein.treinnr
    trein.soort = trein_node.find('{%s}TreinSoort' % namespace).text
    trein.soort_code = trein_node.find('{%s}TreinSoort' % namespace).attrib['Code']
    trein.vervoerder = trein_node.find('{%s}Vervoerder' % namespace).text

    # Fix voor verkeerde naam 'NS Interna' voor NS International (zie #1):
    if trein.vervoerder == 'NS Interna' or trein.vervoerder == 'NS Int':
        trein.vervoerder = 'NS International'
    elif trein.vervoerder == 'Locon Bene':
        trein.vervoerder = 'Locon Benelux'
    
    # Treinnaam
    naam_node = trein_node.find('{%s}TreinNaam' % namespace)
    if naam_node != None:
        trein.treinnaam = naam_node.text

    # Status:
    trein.status = trein_node.find('{%s}TreinStatus' % namespace).text

    # Vertrektijd en vertraging:
    trein.vertrek = isodate.parse_datetime(trein_node.find('{%s}VertrekTijd[@InfoStatus="Gepland"]' % namespace).text)
    trein.vertrek_actueel = isodate.parse_datetime(trein_node.find('{%s}VertrekTijd[@InfoStatus="Actueel"]' % namespace).text)

    trein.vertraging = iso_duur_naar_seconden(trein_node.find('{%s}ExacteVertrekVertraging' % namespace).text)
    trein.vertraging_gedempt = iso_duur_naar_seconden(trein_node.find('{%s}GedempteVertrekVertraging' % namespace).text)

    # Gepland en actueel vertrekspoor:
    trein.vertrekspoor = parse_vertreksporen(trein_node.findall('{%s}TreinVertrekSpoor[@InfoStatus="Gepland"]' % namespace), namespace)
    trein.vertrekspoor_actueel = parse_vertreksporen(trein_node.findall('{%s}TreinVertrekSpoor[@InfoStatus="Actueel"]' % namespace), namespace)

    # Geplande en actuele bestemming:
    trein.eindbestemming = parse_stations(trein_node.findall('{%s}TreinEindBestemming[@InfoStatus="Gepland"]' % namespace), namespace)
    trein.eindbestemming_actueel = parse_stations(trein_node.findall('{%s}TreinEindBestemming[@InfoStatus="Actueel"]' % namespace), namespace)

    # Diverse statusvariabelen:
    trein.reserveren = parse_boolean(trein_node.find('{%s}Reserveren' % namespace).text)
    trein.toeslag = parse_boolean(trein_node.find('{%s}Toeslag' % namespace).text)
    nin_node = trein_node.find('{%s}NietInstappen' % namespace)

    if nin_node != None:
        trein.niet_instappen = parse_boolean(nin_node.text)
    else:
        __logger__.debug("Element NietInstappen ontbreekt (trein %s/%s)", trein.treinnr, trein.rit_station.code)

    trein.rangeerbeweging = parse_boolean(trein_node.find('{%s}RangeerBeweging' % namespace).text)
    trein.speciaal_kaartje = parse_boolean(trein_node.find('{%s}SpeciaalKaartje' % namespace).text)
    trein.achterblijven = parse_boolean(trein_node.find('{%s}AchterBlijvenAchtersteTreinDeel' % namespace).text)

    # Parse wijzigingsberichten:
    trein.wijzigingen = []
    for wijziging_node in trein_node.findall('{%s}Wijziging' % namespace):
        trein.wijzigingen.append(parse_wijziging(wijziging_node, namespace))

    # Reistips:
    trein.reistips = []
    for reistip_node in trein_node.findall('{%s}ReisTip' % namespace):
        reistip = ReisTip(reistip_node.find('{%s}ReisTipCode' % namespace).text)

        reistip.stations = parse_stations(reistip_node.findall('{%s}ReisTipStation' % namespace), namespace)
        trein.reistips.append(reistip)

    # Instaptips:
    trein.instaptips = []
    for instaptip_node in trein_node.findall('{%s}InstapTip'):
        instaptip = InstapTip()

        instaptip.uitstap_station = parse_station(instaptip_node.find('{%s}InstapTipUitstapStation' % namespace), namespace)
        instaptip.eindbestemming = parse_station(instaptip_node.find('{%s}InstapTipTreinEindBestemming' % namespace), namespace)
        instaptip.treinsoort = instaptip_node.find('{%s}InstapTipTreinSoort' % namespace).text
        instaptip.instap_spoor = parse_spoor(instaptip_node.find('{%s}InstapTipVertrekSpoor' % namespace), namespace)
        instaptip.instap_vertrek = isodate.parse_datetime(instaptip_node.find('{%s}InstapTipVertrekTijd' % namespace).text)

        trein.instaptips.append(instaptip)

    # Overstaptips:
    trein.overstaptips = []
    for overstaptip_node in trein_node.findall('{%s}OverstapTip' % namespace):
        overstaptip = OverstapTip()

        overstaptip.bestemming = parse_station(overstaptip_node.find('{%s}OverstapTipBestemming' % namespace), namespace)
        overstaptip.overstap_station = parse_station(overstaptip_node.find('{%s}OverstapTipOverstapStation' % namespace), namespace)

        trein.overstaptips.append(overstaptip)

    # Verkorte route
    trein.verkorte_route = []
    trein.verkorte_route_actueel = []

    trein.verkorte_route = parse_stations(trein_node.findall('{%s}VerkorteRoute[@InfoStatus="Gepland"]/{%s}Station' % (namespace, namespace)), namespace)
    trein.verkorte_route_actueel = parse_stations(trein_node.findall('{%s}VerkorteRoute[@InfoStatus="Actueel"]/{%s}Station'% (namespace, namespace)), namespace)

    # Parse treinvleugels
    trein.vleugels = []

    for vleugel_node in trein_node.findall('{%s}TreinVleugel' % namespace):
        vleugel_eindbestemming = parse_station(vleugel_node.find('{%s}TreinVleugelEindBestemming[@InfoStatus="Gepland"]' % namespace), namespace)
        vleugel = TreinVleugel(vleugel_eindbestemming)

        # Vertrekspoor en bestemming voor de vleugel:
        vleugel.vertrekspoor = parse_vertreksporen(vleugel_node.findall('{%s}TreinVleugelVertrekSpoor[@InfoStatus="Gepland"]' % namespace), namespace)
        vleugel.vertrekspoor_actueel = parse_vertreksporen(vleugel_node.findall('{%s}TreinVleugelVertrekSpoor[@InfoStatus="Actueel"]' % namespace), namespace)
        vleugel.eindbestemming_actueel = parse_station(vleugel_node.find('{%s}TreinVleugelEindBestemming[@InfoStatus="Actueel"]' % namespace), namespace)

        # Stopstations:
        vleugel.stopstations = parse_stations(vleugel_node.findall('{%s}StopStations[@InfoStatus="Gepland"]/{%s}Station' % (namespace, namespace)), namespace)
        vleugel.stopstations_actueel = parse_stations(vleugel_node.findall('{%s}StopStations[@InfoStatus="Actueel"]/{%s}Station' % (namespace, namespace)), namespace)

        # Materieel per vleugel:
        vleugel.materieel = []
        for mat_node in vleugel_node.findall('{%s}MaterieelDeelDVS' % namespace):
            mat = Materieel()
            mat.soort = mat_node.find('{%s}MaterieelSoort' % namespace).text
            mat.aanduiding = mat_node.find('{%s}MaterieelAanduiding' % namespace).text
            mat.lengte = mat_node.find('{%s}MaterieelLengte' % namespace).text
            mat.eindbestemming = parse_station(mat_node.find('{%s}MaterieelDeelEindBestemming[@InfoStatus="Gepland"]' % namespace), namespace)
            mat.eindbestemming_actueel = parse_station(mat_node.find('{%s}MaterieelDeelEindBestemming[@InfoStatus="Actueel"]' % namespace), namespace)

            vertrekpositie_node = mat_node.find('{%s}MaterieelDeelVertrekPositie' % namespace)
            if vertrekpositie_node != None:
                mat.vertrekpositie = vertrekpositie_node.text

            volgorde_vertrek_node = mat_node.find('{%s}MaterieelDeelVolgordeVertrek' % namespace)
            if volgorde_vertrek_node != None:
                mat.volgorde_vertrek = volgorde_vertrek_node.text

            matnummer_node = mat_node.find('{%s}MaterieelNummer' % namespace)
            if matnummer_node != None:
                mat.matnummer = matnummer_node.text

            vleugel.materieel.append(mat)

        # Wijzigingsbericht(en):
        vleugel.wijzigingen = []
        for wijziging_node in vleugel_node.findall('{%s}Wijziging' % namespace):
            vleugel.wijzigingen.append(parse_wijziging(wijziging_node, namespace))

        # Voeg vleugel aan trein toe:
        trein.vleugels.append(vleugel)

    return trein


def parse_trein_dict(trein_dict, statisch=False):
    """
    Vertaal een dict over een trein (uit de injectiefeed)
    naar een Trein object.
    """

    # Maak trein object:
    trein = Trein()
    trein.statisch = statisch
    trein.wijzigingen = []

    # Metadata over rit:
    if int(trein_dict['service_number']) == 0:
        trein.rit_id = 'i%s' % trein_dict['service_id']
    else:
        trein.rit_id = trein_dict['service_number']

    trein.rit_datum = isodate.parse_date(trein_dict['service_date'])
    trein.rit_station = Station(trein_dict['stop_code'].upper(), None)
    trein.rit_timestamp = datetime.datetime.now(pytz.utc)

    # Treinnummer, soort/formule, etc:
    trein.treinnr = trein_dict['service_number']
    trein.soort = trein_dict['transmode_text']
    trein.soort_code = trein_dict['transmode_code']
    trein.vervoerder = trein_dict['company']

    # Status:
    trein.status = 0

    # Vertrektijd en vertraging:
    trein.vertrek = isodate.parse_datetime(trein_dict['departure']).astimezone (pytz.utc)
    trein.vertrek_actueel = trein.vertrek

    trein.vertraging = 0
    trein.vertraging_gedempt = 0

    if 'departure_delay' in trein_dict:
        trein.vertraging = int(trein_dict['departure_delay']) * 60
        trein.vertraging_gedempt = trein.vertraging

    # Gepland en actueel vertrekspoor:
    trein.vertrekspoor = []
    if trein_dict['platform'] != None:
        trein.vertrekspoor.append(Spoor(trein_dict['platform']))
    trein.vertrekspoor_actueel = trein.vertrekspoor

    # Geplande en actuele bestemming:
    trein.eindbestemming = [Station(trein_dict['destination_code'], trein_dict['destination_text'])]
    trein.eindbestemming_actueel = trein.eindbestemming

    # Vleugel:
    vleugel = TreinVleugel(trein.eindbestemming[0])
    vleugel.eindbestemming_actueel = vleugel.eindbestemming
    vleugel.stopstations = []
    for stop in trein_dict['stops']:
        vleugel.stopstations.append(Station(stop[0], stop[1]))
    vleugel.stopstations_actueel = vleugel.stopstations

    trein.vleugels = [vleugel]

    if 'do_not_board' in trein_dict:
        trein.niet_instappen = trein_dict['do_not_board']

    # Verkorte route
    trein.verkorte_route = []
    if 'via' in trein_dict:
        for via_station in trein_dict['via']:
            trein.verkorte_route.append(Station(via_station[0], via_station[1]))
    trein.verkorte_route_actueel = trein.verkorte_route

    # Trein is opgeheven
    if 'cancelled' in trein_dict and trein_dict['cancelled'] is True:
        trein.wijzigingen.append(Wijziging('32'))

    return trein


def parse_stations(station_nodes, namespace):
    """
    Vertaal een node met stations naar een list van Station objecten.
    """

    stations = []

    for station_node in station_nodes:
        stations.append(parse_station(station_node, namespace))

    return stations


def parse_station(station_element, namespace):
    """
    Vertaal een XML node met een station naar een Station object.
    """

    station_object = Station(
        station_element.find(
            '{%s}StationCode' % namespace).text,
        station_element.find(
            '{%s}LangeNaam' % namespace).text
        )

    station_object.korte_naam = station_element.find('{%s}KorteNaam' % namespace).text
    station_object.middel_naam = station_element.find('{%s}MiddelNaam' % namespace).text
    uic_node = station_element.find('{%s}UICCode' % namespace)
    station_object.station_type = station_element.find('{%s}Type' % namespace).text
    if uic_node is not None:
        station_object.uic = uic_node.text

    return station_object


def parse_wijziging(wijziging_node, namespace):
    """
    Vertaal een XML node met een wijziging naar een Wijziging object.
    """

    wijziging = Wijziging(wijziging_node.find(
        '{%s}WijzigingType' % namespace).text)

    oorzaak_node = wijziging_node.find(
        '{%s}WijzigingOorzaakKort' % namespace)
    if oorzaak_node != None:
        wijziging.oorzaak = oorzaak_node.text

    oorzaak_lang_node = wijziging_node.find(
        '{%s}WijzigingOorzaakLang' % namespace)
    if oorzaak_lang_node != None:
        wijziging.oorzaak_lang = oorzaak_lang_node.text

    station_node = wijziging_node.find(
        '{%s}WijzigingStation' % namespace)
    if station_node != None:
        wijziging.station = parse_station(station_node, namespace)

    return wijziging


def parse_vertreksporen(spoor_nodes, namespace):
    """
    Vertaal een XML node met vertreksporen naar een list met Spoor objecten.
    """
    sporen = []

    for spoor_node in spoor_nodes:
        sporen.append(parse_spoor(spoor_node, namespace))

    return sporen


def parse_spoor(spoor_node, namespace):
    """
    Vertaal een XML node met een vertrekspoor naar een Spoor object.
    """

    spoor = Spoor(spoor_node.find(
        '{%s}SpoorNummer' % namespace).text)

    # Zoek eventuele fase:
    fase_node = spoor_node.find(
        '{%s}SpoorFase' % namespace)
    if fase_node is not None:
        spoor.fase = fase_node.text

    return spoor


def parse_boolean(value):
    """
    Vertaal een booleaanse waarde in een DVS bericht (string 'J' of 'N')
    naar True of False.
    """

    if value == 'J':
        return True
    else:
        return False

class Station(object):
    """
    Class om informatie over een station in te bewaren.
    """

    code = None
    korte_naam = None
    middel_naam = None
    lange_naam = None
    uic = None
    station_type = None

    def __init__(self, code, lange_naam):
        self.code = code
        self.lange_naam = lange_naam
        self.middel_naam = lange_naam
        self.korte_naam = lange_naam

    def __repr__(self):
        return '<station %s %s>' % (self.code, self.lange_naam)


class Spoor(object):
    """
    Class om spoornummers te bewaren. Een spoor bestaat uit een nummer
    en optioneel een fase (a, b, ...)
    """

    nummer = None
    fase = None

    def __init__(self, nummer, fase=None):
        self.nummer = nummer
        self.fase = fase

    def __repr__(self):
        if self.fase != None:
            return '%s%s' % (self.nummer, self.fase)
        else:
            return self.nummer


class Trein(object):
    """
    Class om treinen in te bewaren, inclusief metadata.
    """

    rit_id = None
    rit_station = None
    rit_datum = None
    rit_timestamp = None
    vertrokken_timestamp = None

    treinnr = None
    eindbestemming = []
    eindbestemming_actueel = []
    vervoerder = None
    treinnaam = None

    status = 0

    soort = None
    soort_code = None
    
    vertrek = None
    vertrek_actueel = None
    
    vertraging = 0
    vertraging_gedempt = 0

    vertrekspoor = []
    vertrekspoor_actueel = []

    reserveren = False
    toeslag = False
    niet_instappen = False
    speciaal_kaartje = False
    rangeerbeweging = False
    achterblijven = False

    verkorte_route = []
    verkorte_route_actueel = []

    vleugels = []
    wijzigingen = []
    reistips = []
    instaptips = []
    overstaptips = []

    statisch = False

    def lokaal_vertrek(self):
        """
        Geef de geplande vertrektijd terug in lokale (NL) tijd.
        """

        tijdzone = pytz.timezone('Europe/Amsterdam')
        return self.vertrek.astimezone(tijdzone)

    def lokaal_vertrek_actueel(self):
        """
        Geef de actuele vertrektijd terug in lokale (NL) tijd.
        """

        tijdzone = pytz.timezone('Europe/Amsterdam')
        return self.vertrek_actueel.astimezone(tijdzone)

    def is_gewijzigd_vertrekspoor(self):
        """
        Geeft True terug indien het vertrekspoor gewijzigd is.
        """

        return (self.vertrekspoor != self.vertrekspoor_actueel)

    def is_opgeheven(self):
        """
        Geef met een boolean waarde aan of de trein opgeheven is of niet.
        Deze functie leest hiervoor de wijzigingen op treinniveau uit.
        """

        for wijziging in self.wijzigingen:
            if wijziging.wijziging_type == '32':
                return True

        return False

    def treinnaam_str(self, taal='nl', alleen_belangrijk=True, trein=None):
        """
        Geeft de treinnaam als string terug. Wanneer de treinnaam misbruikt
        wordt voor reisinfo, wordt de treinnaam eventueel vertaald naar een
        andere taal zodat de reisinformatie ook in een andere taal beschikbaar
        is.
        """

        if taal == 'en':
            # Toeslag IC direct
            if self.treinnaam == 'Toeslag Schiphol-Rotterdam vv':
                return 'Supplement between Schiphol and Rotterdam v.v.'

        return self.treinnaam

    def wijzigingen_str(self, taal='nl', alleen_belangrijk=True, trein=None, geen_station_opmerkingen=False):
        """
        Geef alle wijzigingsberichten op trein- en vleugelniveau
        terug als list met strings. Berichten op vleugelniveau krijgen een
        prefix met de vleugelbestemming als de trein meerdere vleugels heeft.

        De parameter alleen_belangrijk geeft alleen 'belangrijke' bepaalt of
        alle wijzigingsberichten worden teruggegeven, of alleen de belangrijke.
        Dit wordt bepaald door Wijziging.is_belangrijk().

        De parameter geen_station_opmerkingen bepaalt (indien True) dat alleen
        berichten die op ritniveau nuttig zijn worden teruggegeven.
        """

        wijzigingen = []

        # Eerst de wijzigingen op treinniveau:
        for wijziging in self.wijzigingen:
            if wijziging.wijziging_type != '40' and \
                    (wijziging.is_belangrijk() or alleen_belangrijk != True) and \
                    (wijziging.is_stations_opmerking() is False or geen_station_opmerkingen is False):
                # Voeg bericht toe aan list met berichten:
                wijzigingen.append(wijziging.to_str(taal, trein))

        # Dan de wijzigingen op vleugelniveau:
        for vleugel in self.vleugels:
            for wijziging in vleugel.wijzigingen:
                # Filter op type 40 (status gewijzigd)
                # en op type 20 (gewijzigd vertrekspoor)
                # Type 20 zit bijna altijd al op treinniveau
                if wijziging.wijziging_type != '40' and \
                                wijziging.wijziging_type != '20' and \
                        (wijziging.is_belangrijk() or alleen_belangrijk != True) and \
                        (wijziging.is_stations_opmerking() is False or geen_station_opmerkingen is False):
                    # Vertaal Wijziging object naar string:
                    bericht = wijziging.to_str(taal, trein)

                    # Zet de vleugelbestemming voor het bericht
                    # indien deze trein uit meerdere vleugels bestaat:
                    if len(self.vleugels) > 1:
                        bericht = '%s: %s' % \
                        (vleugel.eindbestemming.middel_naam, bericht)

                    # Voeg bericht toe aan list met berichten:
                    wijzigingen.append(bericht)

        return wijzigingen

    def tips(self, taal='nl'):
        """
        Vertaal de reistips naar strings en geef alle reistips
        terug als list met strings. Deze functie geeft alle soorten
        reistips terug, inclusief InstapTips en OverstapTips.
        """

        tips = []
        opgeheven = self.is_opgeheven()

        if opgeheven != True:
            # De volgende tips worden alleen gevuld indien
            # de trein niet opgeheven is
            for tip in self.reistips:
                tips.append(tip.to_str(taal))
            for tip in self.instaptips:
                tips.append(tip.to_str(taal))
            for tip in self.overstaptips:
                tips.append(tip.to_str(taal))

            if self.niet_instappen == True:
                tips.append(self.niet_instappen_str(taal))

            if self.achterblijven == True:
                tips.append(self.achterblijven_str(taal))

        # De volgende tips worden altijd gegeven (ook voor opgeheven treinen),
        # aangezien opgeheven trein hiermee herkenbaar blijft
        if self.speciaal_kaartje == True:
            tips.append(self.speciaal_kaartje_str(taal))

        if self.reserveren == True:
            tips.append(self.reserveren_str(taal))

        if self.toeslag == True:
            tips.append(self.toeslag_str(taal))

        return tips

    def niet_instappen_str(self, taal):
        """
        Geef een tekstmelding terug als de trein gemarkeerd is
        als 'Niet Instappen'.
        """

        if self.niet_instappen == True:
            if taal == 'en':
                return 'Do not board'
            else:
                return 'Niet instappen'

    def speciaal_kaartje_str(self, taal):
        """
        Geef een tekstmelding terug als voor deze trein een speciaal kaartje
        vereist is.
        """

        if self.speciaal_kaartje == True:
            if taal == 'en':
                return 'Special ticket required'
            else:
                return 'Bijzonder ticket'

    def achterblijven_str(self, taal):
        """
        Geef een tekstmelding terug als het achterste treindeel achterblijft.
        """

        if self.achterblijven == True:
            if taal == 'en':
                return 'Rear trainpart: do not board'
            else:
                return 'Achterste treindeel blijft achter'

    def toeslag_str(self, taal):
        """
        Geef een tekstmelding terug als een toeslag verplicht is.
        """

        if self.toeslag == True:
            if taal == 'en':
                return 'Supplement required'
            else:
                return 'Toeslag verplicht'

    def reserveren_str(self, taal):
        """
        Geef een tekstmelding terug als reserveren verplicht is.
        """

        if self.reserveren == True:
            if taal == 'en':
                return 'Reservation required'
            else:
                return 'Reservering verplicht'

    def markeer_vertrokken(self):
        self.status = "5"
        self.vertrokken_timestamp = datetime.datetime.now(pytz.utc)

    def is_vertrokken(self):
        return self.status == "5"

    def __repr__(self):
        return '<Trein %-3s %6s v%s +%s %-4s %-3s -- %-4s>' % \
        (self.soort_code, self.rit_id, self.lokaal_vertrek(),
            self.vertraging, self.rit_station.code, self.vertrekspoor_actueel,
            self.eindbestemming_actueel)


class TreinVleugel(object):
    """
    Een treinvleugel is een deel van de trein met een bepaalde eindbestemming,
    materieel en wijzigingen. Een trein kan uit meerdere vleugels bestaan met
    verschillende bestemmingen.
    """

    vertrekspoor = []
    vertrekspoor_actueel = []
    eindbestemming = None
    eindbestemming_actueel = None
    stopstations = []
    stopstations_actueel = []
    materieel = []
    wijzigingen = []

    def __init__(self, eindbestemming):
        self.eindbestemming = eindbestemming
        self.eindbestemming_actueel = eindbestemming


class Materieel(object):
    """
    Class om treinmaterieel bij te houden.
    Elk materieeldeel heeft een eindbestemming en is
    semantisch gezien onderdeel van een treinvleugel.
    """

    soort = None
    aanduiding = None
    lengte = 0
    eindbestemming = None
    eindbestemming_actueel = None
    vertrekpositie = None
    volgorde_vertrek = None
    matnummer = None

    def __init__(self):
        pass

    def treintype(self):
        """
        Geef het treintype terug als string.
        """

        if self.aanduiding != None:
            return '%s-%s' % (self.soort, self.aanduiding)
        else:
            return self.soort

    def is_loc(self):
        """
        Bepaal of dit materieeldeel een locomotief is
        """
        soort = self.treintype()

        if soort == 'E-LOC-1700' or soort == 'TRAXX-E186' or \
        soort == 'TRAXX HSL-E186' or soort == 'E-LOC-TRAX' \
        or soort == 'E-LOC-TR25' or soort == 'BR189-ELOC':
            return True

        return False

    def get_matnummer(self):
        """
        Bereken een leesbaar materieelnummer
        """
        if self.matnummer == None:
            return None

        # Schoon matnummer op:
        matnummer = self.matnummer.lstrip("0-").rstrip("0").rstrip("-")

        # Fix 1-86xxx notatie:
        regex = re.compile("(1)\\-(86)([0-9]{3})")
        match = regex.match(matnummer)

        if match:
            matnummer = "%s%s-%s" % match.group(1, 2, 3)

        return matnummer

class Wijziging(object):
    """
    Class om wijzigingsberichten bij te houden.
    Iedere wijziging wordt geidentificeerd met een code (wijziging_type),
    dit is een numerieke code die te vertalen is naar een concreet bericht.
    Optioneel wordt het bericht aangevuld met stationsinformatie of een oorzaak
    voor een wijziging.
    """

    wijziging_type = 0
    oorzaak = None
    oorzaak_lang = None
    station = None

    def __init__(self, wijziging_type):
        self.wijziging_type = wijziging_type

    def is_belangrijk(self):
        """
        Bepaal of een Wijziging een belangrijk bericht is of niet (voor
        treinreizigers). Op dit moment worden code 10 (vertraging) en
        code 22 (vertrekspoorfixatie) weggefilterd.
        """

        if self.wijziging_type == '22':
            return False
        elif self.wijziging_type == '10':
            # Filter vertraging alleen indien zonder oorzaak
            if self.oorzaak_lang == None:
                return False
            else:
                return True
        else:
            return True

    def is_stations_opmerking(self):
        if self.wijziging_type == '10':
            return True
        elif self.wijziging_type == '20':
            return True
        elif self.wijziging_type == '22':
            return True
        elif self.wijziging_type == '31':
            return True
        elif self.wijziging_type == '32':
            return True
        else:
            return False

    def to_str(self, taal='nl', trein=None):
        """
        Vertaal een wijziging_type naar een concreet bericht in Nederlands
        of Engels (aangegeven met parameter taal). Gebruik 'nl' of 'en'.
        """

        if self.wijziging_type == '10':
            if taal == 'en':
                return 'Delayed%s' % self.oorzaak_prefix(taal)
            else:
                return 'Later vertrek%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '20':
            if trein == None:
                if taal == 'en':
                    return 'Platform has been changed'
                else:
                    return 'Vertrekspoor gewijzigd'
            else:
                if taal == 'en':
                    return 'Platform changed, departs from platform %s' % \
                    '/'.join(str(spoor) for spoor in trein.vertrekspoor_actueel)
                else:
                    return 'Spoorwijziging, vertrekt van spoor %s' % \
                    '/'.join(str(spoor) for spoor in trein.vertrekspoor_actueel)
        elif self.wijziging_type == '22':
            if taal == 'en':
                return 'Platform has been allocated'
            else:
                return 'Vertrekspoor toegewezen'
        elif self.wijziging_type == '30':
            if taal == 'en':
                return 'Schedule changed%s' % self.oorzaak_prefix(taal)
            else:
                return 'Gewijzigde dienstregeling%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '31':
            if taal == 'en':
                return 'Additional train%s' % self.oorzaak_prefix(taal)
            else:
                return 'Extra trein%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '32':
            if taal == 'en':
                return 'Train is cancelled%s' % self.oorzaak_prefix(taal)
            else:
                return 'Trein rijdt niet%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '33':
            if taal == 'en':
                return 'Diverted train%s' % self.oorzaak_prefix(taal)
            else:
                return 'Rijdt via een andere route%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '34':
            if taal == 'en':
                return 'Terminates at %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
            else:
                return 'Rijdt niet verder dan %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
        elif self.wijziging_type == '35':
            if taal == 'en':
                return 'Continues to %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
            else:
                return 'Rijdt verder naar %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
        elif self.wijziging_type == '41':
            if taal == 'en':
                return 'Attention, train goes to %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
            else:
                return 'Let op, rijdt naar %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
        elif self.wijziging_type == '50':
            if taal == 'en':
                return 'No real-time information'
            else:
                return 'Geen actuele informatie'
        elif self.wijziging_type == '51':
            if taal == 'en':
                return 'Bus replaces train'
            else:
                return 'Bus vervangt trein'
        else:
            return '%s' % self.wijziging_type

    def oorzaak_prefix(self, taal):
        """
        Geeft een string terug met oorzaak (indien aanwezig)
        Geeft een lege string terug indien de taal Engels is en er geen vertaling
        beschikbaar is. Oorzaken worden namelijk alleen in het Nederlands geboden.
        """

        if self.oorzaak_lang == None:
            return ''
        elif taal == 'en':
            oorzaak_vertaald = self.oorzaak_engels()

            if oorzaak_vertaald != None:
                return ' due to %s' % oorzaak_vertaald
            else:
                return ''
        else:
            return ' %s' % self.oorzaak_lang

    def oorzaak_engels(self):
        """
        Vertaal de oorzaak naar Engels (indien een vertaling beschikbaar is).
        """

        vertalingen = {
            'door geplande werkzaamheden': 'planned engineering work',
            'door werkzaamheden': 'engineering work',
            'door onverwachte werkzaamheden': 'unexpected engineering work',
            'door uitgelopen werkzaamheden': 'over-running engineering works',
            'door uitloop van werkzaamheden': 'over-running engineering works',
            'door de aanleg van een nieuw spoor': 'construction of a new track',
            'door een spoedreparatie aan het spoor': 'emergency repairs',
            'door een aangepaste dienstregeling': 'an amended timetable',
            'door te grote vertraging': 'large delay',
            'door te hoog opgelopen vertraging': 'excessive delay',
            'door te veel vertraging in het buitenland': 'excessive delay abroad',
            'door een eerdere verstoring': 'an earlier disruption',
            'door herstelwerkzaamheden': 'reparation works',
            'door een seinstoring': 'signal failure',
            'door een sein- en wisselstoring': 'signalling and points failure',
            'door een sein-en wisselstoring': 'signalling and points failure',
            'door een grote sein- en wisselstoring': 'a large signalling failure',
            'door een storing aan bediensysteem seinen en wissels': 'a control system failure',
            'door een storing in de bediening van seinen': 'a control system failure',
            'door defect materieel': 'a broken down train',
            'door een defecte trein': 'a broken down train',
            'door defecte treinen': 'broken down trains',
            'door een ontspoorde trein': 'a derailed train',
            'door een gestrande trein': 'a stranded train',
            'door een defecte spoorbrug': 'a defective railway bridge',
            'door een beschadigd spoorviaduct': 'a damaged railway bridge',
            'door een beschadigde spoorbrug': 'a damaged railway bridge',
            'door beperkingen in de materieelinzet': 'rolling stock problems',
            'door beperkingen in het buitenland': 'restrictions abroad',
            'door acties van het personeel': 'staff strike',
            'door acties in het buitenland': 'staff strike abroad',
            'door een wisselstoring': 'points failure',
            'door een defect wissel': 'a defective switch',
            'door veel defect materieel': 'numerous broken down trains',
            'door een overwegstoring': 'level crossing failure',
            'door overwegstoringen': 'level crossing failures',
            'door een aanrijding met een persoon': 'a person hit by a train',
            'door een aanrijding': 'a collision',
            'door een aanrijding met een dier': 'a collision with an animal',
            'door een aanrijding met een voertuig': 'a collision with a vehicle',
            'door een auto op het spoor': 'a car on the track',
            'door mensen op het spoor': 'persons on the track',
            'door een dier op het spoor': 'an animal on the track',
            'door een boom op het spoor': 'a tree on the track',
            'door een verstoring elders': 'a disruption elsewhere',
            'door een persoon op het spoor': 'a trespassing incident',
            'door een persoon langs het spoor': 'a trespassing incident',
            'door een defect spoor': 'a defective rail',
            'door een defect aan het spoor': 'a defective rail',
            'door gladde sporen': 'slippery rail',
            'door een defecte bovenleiding': 'overhead wire problems',
            'door een beschadigde bovenleiding': 'a damaged overhead wire',
            'door een beschadigde overweg': 'a damaged level crossing',
            'door een defecte overweg': 'a defective level crossing',
            'door een versperring': 'an obstruction on the line',
            'door inzet van de brandweer': 'deployment of the fire brigade',
            'door inzet van de politie': 'police action',
            'door brand in een trein': 'fire in a train',
            'op last van de politie': 'restrictions imposed by the police',
            'op last van de brandweer': 'restrictions imposed by the fire brigade',
            'door politieonderzoek': 'police investigation',
            'door vandalisme': 'vandalism',
            'door inzet van hulpdiensten': 'an emergency call',
            'door een stroomstoring': 'power disruption',
            'door stormschade': 'storm damage',
            'door een bermbrand': 'a lineside fire',
            'door diverse oorzaken': 'various reasons',
            'door meerdere verstoringen': 'multiple disruptions',
            'door koperdiefstal': 'copper theft',
            'verwachte weersomstandigheden': 'expected weather conditions',
            'door de weersomstandigheden': 'bad weather conditions',
            'sneeuw': 'snow',
            'door rijp aan de bovenleiding': 'frost on the overhead wires',
            'door ijzelvorming aan de bovenleiding': 'ice on the overhead wires',
            'door harde wind op de Hogesnelheidslijn': 'strong winds on the high-speed line',
            'door het onschadelijk maken van een bom uit de Tweede Wereldoorlog': 'defusing a bomb from World War II',
            'door het onschadelijk maken van een bom uit de 2e WO': 'defusing a bomb from World War II',
            'door een evenement': 'an event',
            'door een sein-en overwegstoring': 'signalling failure and a level crossing failure',
            'door een sein- en overwegstoring': 'signalling failure and a level crossing failure',
            'door technisch onderzoek': 'technical inspection',
            'door een brandmelding': 'a fire alarm',
            'door een voorwerp in de bovenleiding': 'an obstacle in the overhead wire',
            'door een voorwerp op het spoor': 'an obstacle on the track',
            'door rommel op het spoor': 'rubbish on the track',
            'door grote drukte': 'large crowds',
            'door blikseminslag': 'lightning',
            'door wateroverlast': 'flooding',
            'door problemen op het spoor in het buitenland': 'railway problems abroad',
            'door problemen in het buitenland': 'railway problems abroad',
            'door een storing in een tunnel': 'a problem in a tunnel',
            'door hinder op het spoor': 'interference on the line',
            'veiligheidsredenen': 'safety reasons',
            'door het onverwacht ontbreken van personeel': 'missing crew',
            'door een vervangende trein': 'a replacement train',
            'door het vervangen van een spoorbrug': 'replacement of a railway bridge',
            'door Koningsdag': 'King\'s day',
            'door de Vierdaagse': 'the Four Days Marches',
            'door nog onbekende oorzaak': 'a yet unknown reason'
        }

        if self.oorzaak_lang in vertalingen:
            return vertalingen[self.oorzaak_lang]
        else:
            __logger__.warn("Geen Engelse vertaling voor '%s'", self.oorzaak_lang)
            return None

class ReisTip(object):
    """
    Class om reistips in te bewaren. Een reistip is voor reizigers belangrijke
    informatie zoals stations die worden overgeslagen. De variabele code
    bepaalt de exacte boodschap, aan deze boodschap kunnen 0 of meer stations
    worden meegegeven.
    """

    code = None
    stations = []

    def __init__(self, code):
        self.code = code

    def to_str(self, taal='nl'):
        """
        Vertaal de reistip naar een concreet bericht in de gegeven taal.
        """

        if self.code == 'STNS':
            if taal == 'en':
                return 'Does not call at %s' % self.stations_str(taal)
            else:
                return 'Stopt niet in %s' % self.stations_str(taal)
        elif self.code == 'STO':
            if taal == 'en':
                return 'Also calls at %s' % self.stations_str(taal)
            else:
                return 'Stopt ook in %s' % self.stations_str(taal)
        elif self.code == 'STVA':
            if taal == 'en':
                return 'Calls at all stations after %s' % self.stations_str(taal)
            else:
                return 'Stopt vanaf %s op alle stations' % self.stations_str(taal)
        elif self.code == 'STNVA':
            if taal == 'en':
                return 'Does not call at intermediate stations after %s' % self.stations_str(taal)
            else:
                return 'Stopt vanaf %s niet op tussengelegen stations' % self.stations_str(taal)
        elif self.code == 'STT':
            if taal == 'en':
                return 'Calls at all stations until %s' % self.stations_str(taal)
            else:
                return 'Stopt tot %s op alle tussengelegen stations' % self.stations_str(taal)
        elif self.code == 'STNT':
            if taal == 'en':
                return 'First stop at %s' % self.stations_str(taal)
            else:
                return 'Stopt tot %s niet op tussengelegen stations' % self.stations_str(taal)
        elif self.code == 'STAL':
            if taal == 'en':
                return 'Calls at all stations'
            else:
                return 'Stopt op alle tussengelegen stations'
        elif self.code == 'STN':
            if taal == 'en':
                return 'Does not call at intermediate stations'
            else:
                return 'Stopt niet op tussengelegen stations'
        else:
            return self.code

    def stations_str(self, taal='nl'):
        """
        Vertaal de lijst met stations naar een geformatteerde string in de
        gegeven taal.
        """
        if taal == 'en':
            if len(self.stations) <= 2:
                return ' and '.join(station.lange_naam for station in self.stations)
            else:
                return ', '.join(station.lange_naam for station in self.stations[:-1]) + ', and ' + self.stations[-1].lange_naam
        else:
            if len(self.stations) <= 2:
                return ' en '.join(station.lange_naam for station in self.stations)
            else:
                return ', '.join(station.lange_naam for station in self.stations[:-1]) + ' en ' + self.stations[-1].lange_naam

class InstapTip(object):
    """
    Class om instaptips te bewaren. Een instaptip is een tip voor reizigers
    dat een alternatieve trein eerder op een bepaald station is (bijvoorbeeld
    een intercity die eerder een knooppunt bereikt).
    """

    treinsoort = None
    treinsoort_code = None
    uitstap_station = None
    eindbestemming = None
    instap_vertrek = None
    instap_spoor = None

    def __init__(self):
        pass

    def to_str(self, taal='nl'):
        """
        Vertaal de instaptip naar een concreet bericht (string)
        in de gegeven taal.
        """

        tijdzone = pytz.timezone('Europe/Amsterdam')

        if taal == 'en':
            return '%s %s to %s reaches %s sooner' % (self.treinsoort,
                self.instap_vertrek.astimezone(tijdzone).strftime('%H:%M'),
                self.eindbestemming.lange_naam, self.uitstap_station.lange_naam)
        else:
            return '%s %s naar %s is eerder in %s' % (self.treinsoort,
                self.instap_vertrek.astimezone(tijdzone).strftime('%H:%M'),
                self.eindbestemming.lange_naam, self.uitstap_station.lange_naam)

class OverstapTip(object):
    """
    Class om overstaptips te bewaren. Een overstaptip is een tip dat om een
    bepaalde bestemming te bereiken op een overstapstation moet worden
    overgestapt.
    """

    bestemming = None
    overstap_station = None

    def __init__(self):
        pass

    def to_str(self, taal='nl'):
        """
        Vertaal de overstaptip naar een concreet bericht (string)
        in de gegeven taal.
        """

        if taal == 'en':
            return 'For %s, change at %s' % (self.bestemming.lange_naam,
                self.overstap_station.lange_naam)
        else:
            return 'Voor %s overstappen in %s' % (self.bestemming.lange_naam,
                self.overstap_station.lange_naam)


class OngeldigDvsBericht(Exception):
    """
    Exception voor ongeldige DVS berichten
    """

    # Verder een standaard Exception

    pass

def iso_duur_naar_seconden(string):
    """
    Vertaal een ISO tijdsduur naar seconden.
    Deze functie houdt rekening met negatieve duur
    (in tegenstelling tot isodate).
    """

    if len(string) > 0:
        if string[0] == '-':
            return isodate.parse_duration(string[1:]).seconds * -1

    return isodate.parse_duration(string).seconds
