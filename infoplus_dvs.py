"""
Module om DVS berichten uit InfoPlus te kunnen verwerken.
"""

import xml.etree.cElementTree as ET
import isodate
import pytz
import logging

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
    product = root.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisInformatieProductDVS')
    vertrekstaat = product.find('{urn:ndov:cdm:trein:reisinformatie:data:2}DynamischeVertrekStaat')
    trein_node = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Trein')

    # Maak trein object:
    trein = Trein()
    
    # Metadata over rit:
    trein.rit_id = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitId').text
    trein.rit_datum = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitDatum').text
    trein.rit_station = parse_station(vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitStation'))
    trein.rit_timestamp = isodate.parse_datetime(product.attrib.get('TimeStamp'))
    
    # Treinnummer, soort/formule, etc:
    trein.treinnr = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinNummer').text
    trein.soort = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').text
    trein.soort_code = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').attrib['Code']
    trein.vervoerder = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Vervoerder').text

    # Status:
    trein.status = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinStatus').text

    # Vertrektijd en vertraging:
    trein.vertrek = isodate.parse_datetime(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Gepland"]').text)
    trein.vertrek_actueel = isodate.parse_datetime(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Actueel"]').text)

    trein.vertraging = isodate.parse_duration(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ExacteVertrekVertraging').text)
    trein.vertraging_gedempt = isodate.parse_duration(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}GedempteVertrekVertraging').text)

    # Gepland en actueel vertrekspoor:
    trein.vertrekspoor = parse_vertreksporen(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Gepland"]'))
    trein.vertrekspoor_actueel = parse_vertreksporen(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Actueel"]'))

    # Geplande en actuele bestemming:
    trein.eindbestemming = parse_stations(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Gepland"]'))
    trein.eindbestemming_actueel = parse_stations(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Actueel"]'))

    # Diverse statusvariabelen:
    trein.reserveren = parse_boolean(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Reserveren').text)
    trein.toeslag = parse_boolean(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Toeslag').text)
    nin_node = trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}NietInstappen')

    if nin_node != None:
        trein.niet_instappen = parse_boolean(nin_node.text)
    else:
        __logger__.warn("Element NietInstappen ontbreekt (trein %s/%s)", trein.treinnr, trein.rit_station.code)

    trein.rangeerbeweging = parse_boolean(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RangeerBeweging').text)
    trein.speciaal_kaartje = parse_boolean(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpeciaalKaartje').text)
    trein.achterblijven = parse_boolean(trein_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}AchterBlijvenAchtersteTreinDeel').text)

    # Parse wijzigingsberichten:
    trein.wijzigingen = []
    for wijziging_node in trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}Wijziging'):
        trein.wijzigingen.append(parse_wijziging(wijziging_node))

    # Reistips:
    trein.reistips = []
    for reistip_node in trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTip'):
        reistip = ReisTip(reistip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTipCode').text)

        reistip.stations = parse_stations(reistip_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTipStation'))
        trein.reistips.append(reistip)

    # Instaptips:
    trein.instaptips = []
    for instaptip_node in trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTip'):
        instaptip = InstapTip()

        instaptip.uitstap_station = parse_station(instaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipUitstapStation'))
        instaptip.eindbestemming = parse_station(instaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipTreinEindBestemming'))
        instaptip.treinsoort = instaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipTreinSoort').text
        instaptip.instap_spoor = parse_spoor(instaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipVertrekSpoor'))
        instaptip.instap_vertrek = isodate.parse_datetime(instaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipVertrekTijd').text)

        trein.instaptips.append(instaptip)

    # Overstaptips:
    trein.overstaptips = []
    for overstaptip_node in trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTip'):
        overstaptip = OverstapTip()

        overstaptip.bestemming = parse_station(overstaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTipBestemming'))
        overstaptip.overstap_station = parse_station(overstaptip_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTipOverstapStation'))

        trein.overstaptips.append(overstaptip)

    # Verkorte route
    trein.verkorte_route = []
    trein.verkorte_route_actueel = []

    trein.verkorte_route = parse_stations(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}VerkorteRoute[@InfoStatus="Gepland"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))
    trein.verkorte_route_actueel = parse_stations(trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}VerkorteRoute[@InfoStatus="Actueel"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))

    # Parse treinvleugels
    trein.vleugels = []

    for vleugel_node in trein_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugel'):
        vleugel_eindbestemming = parse_station(vleugel_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelEindBestemming[@InfoStatus="Gepland"]'))
        vleugel = TreinVleugel(vleugel_eindbestemming)

        # Vertrekspoor en bestemming voor de vleugel:
        vleugel.vertrekspoor = parse_vertreksporen(vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Gepland"]'))
        vleugel.vertrekspoor_actueel = parse_vertreksporen(vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Actueel"]'))
        vleugel.eindbestemming_actueel = parse_station(vleugel_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelEindBestemming[@InfoStatus="Actueel"]'))

        # Stopstations:
        vleugel.stopstations = parse_stations(vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}StopStations[@InfoStatus="Gepland"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))
        vleugel.stopstations_actueel = parse_stations(vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}StopStations[@InfoStatus="Actueel"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))

        # Materieel per vleugel:
        vleugel.materieel = []
        for mat_node in vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelDVS'):
            mat = Materieel()
            mat.soort = mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelSoort').text
            mat.aanduiding = mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelAanduiding').text
            mat.lengte = mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelLengte').text
            mat.eindbestemming = parse_station(mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelEindBestemming[@InfoStatus="Gepland"]'))
            mat.eindbestemming_actueel = parse_station(mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelEindBestemming[@InfoStatus="Actueel"]'))

            vertrekpositie_node = mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelVertrekPositie')
            if vertrekpositie_node != None:
                mat.vertrekpositie = vertrekpositie_node.text

            volgorde_vertrek_node = mat_node.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelVolgordeVertrek')
            if volgorde_vertrek_node != None:
                mat.volgorde_vertrek = volgorde_vertrek_node.text

            vleugel.materieel.append(mat)

        # Wijzigingsbericht(en):
        vleugel.wijzigingen = []
        for wijziging_node in vleugel_node.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}Wijziging'):
            vleugel.wijzigingen.append(parse_wijziging(wijziging_node))

        # Voeg vleugel aan trein toe:
        trein.vleugels.append(vleugel)

    return trein


def parse_stations(station_nodes):
    """
    Vertaal een node met stations naar een list van Station objecten.
    """

    stations = []

    for station_node in station_nodes:
        stations.append(parse_station(station_node))

    return stations


def parse_station(station_element):
    """
    Vertaal een XML node met een station naar een Station object.
    """

    station_object = Station(
        station_element.find(
            '{urn:ndov:cdm:trein:reisinformatie:data:2}StationCode').text,
        station_element.find(
            '{urn:ndov:cdm:trein:reisinformatie:data:2}LangeNaam').text
        )

    station_object.korte_naam = station_element.find('{urn:ndov:cdm:trein:reisinformatie:data:2}KorteNaam').text
    station_object.middel_naam = station_element.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MiddelNaam').text
    station_object.uic = station_element.find('{urn:ndov:cdm:trein:reisinformatie:data:2}UICCode').text
    station_object.station_type = station_element.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Type').text

    return station_object


def parse_wijziging(wijziging_node):
    """
    Vertaal een XML node met een wijziging naar een Wijziging object.
    """

    wijziging = Wijziging(wijziging_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingType').text)
    
    oorzaak_node = wijziging_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingOorzaakKort')
    if oorzaak_node != None:
        wijziging.oorzaak = oorzaak_node.text
    
    oorzaak_lang_node = wijziging_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingOorzaakLang')
    if oorzaak_lang_node != None:
        wijziging.oorzaak_lang = oorzaak_lang_node.text

    station_node = wijziging_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingStation')
    if station_node != None:
        wijziging.station = parse_station(station_node)

    return wijziging


def parse_vertreksporen(spoor_nodes):
    """
    Vertaal een XML node met vertreksporen naar een list met Spoor objecten.
    """
    sporen = []
    
    for spoor_node in spoor_nodes:
        sporen.append(parse_spoor(spoor_node))

    return sporen


def parse_spoor(spoor_node):
    """
    Vertaal een XML node met een vertrekspoor naar een Spoor object.
    """

    spoor = Spoor(spoor_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text)

    # Zoek eventuele fase:
    fase_node = spoor_node.find(
        '{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorFase')
    if (fase_node != None):
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

class Station:
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

    def __repr__(self):
        return '<station %s %s>' % (self.code, self.lange_naam)


class Spoor:
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


class Trein:
    """
    Class om treinen in te bewaren, inclusief metadata.
    """

    rit_id = None
    rit_station = None
    rit_datum = None
    rit_timestamp = None

    treinnr = None
    eindbestemming = []
    eindbestemming_actueel = []
    vervoerder = None

    status = 0

    soort = None
    soort_code = None
    
    vertrek = None
    vertrek_actueel = None
    
    vertraging = None
    vertraging_gedempt = None

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

    def wijzigingen_str(self, taal='nl', alleen_belangrijk=True, trein=None):
        """
        Geef alle wijzigingsberichten op trein- en vleugelniveau
        terug als list met strings. Berichten op vleugelniveau krijgen een
        prefix met de vleugelbestemming als de trein meerdere vleugels heeft.

        De parameter alleen_belangrijk geeft alleen 'belangrijke' bepaalt of
        alle wijzigingsberichten worden teruggegeven, of alleen de belangrijke.
        Dit wordt bepaald door Wijziging.is_belangrijk().
        """

        wijzigingen = []

        # Eerst de wijzigingen op treinniveau:
        for wijziging in self.wijzigingen:
            if wijziging.wijziging_type != '40' and \
            (wijziging.is_belangrijk() or alleen_belangrijk != True):
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
                (wijziging.is_belangrijk() or alleen_belangrijk != True):
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

    def __repr__(self):
        return '<Trein %-3s %6s v%s +%s %-4s %-3s -- %-4s>' % \
        (self.soort_code, self.rit_id, self.lokaal_vertrek(),
            self.vertraging, self.rit_station.code, self.vertrekspoor_actueel,
            self.eindbestemming_actueel)


class TreinVleugel: 
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


class Materieel:
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

class Wijziging:
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

        if self.wijziging_type == '10' or self.wijziging_type == '22':
            return False
        else:
            return True

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
        else:
            return '%s' % self.wijziging_type

    def oorzaak_prefix(self, taal):
        """
        Geeft een string terug met oorzaak (indien aanwezig), inclusief een
        prefix 'i.v.m.'. Geeft een lege string terug indien de taal Engels is,
        oorzaken worden namelijk alleen in het Nederlands geboden.
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
            return ' i.v.m. %s' % self.oorzaak_lang

    def oorzaak_engels(self):
        """
        Vertaal de oorzaak naar Engels (indien een vertaling beschikbaar is).
        """

        vertalingen = {
            'geplande werkzaamheden': 'planned engineering work',
            'eerdere verstoring': 'an earlier disruption',
            'een eerdere verstoring': 'an earlier disruption',
            'herstelwerkzaamheden': 'reparation works',
            'seinstoring': 'signalling problems',
            'een seinstoring': 'signalling problems',
            'sein- en wisselstoring': 'signalling and switch problems',
            'een sein- en wisselstoring': 'signalling and switch problems',
            'defect materieel': 'a broken down train',
            'wisselstoring': 'switch failure',
            'een wisselstoring': 'switch failure',
            'een wisselstoring': 'switch failure',
            'aanrijding met een persoon': 'a person hit by a train',
            'een aanrijding met een persoon': 'a person hit by a train',
            'aanrijding': 'a collision',
            'een aanrijding': 'a collision',
            'aanrijding met een voertuig': 'a collision with a vehicle',
            'een aanrijding met een voertuig': 'a collision with a vehicle',
            'uitgelopen werkzaamheden': 'over-running engineering works',
            'persoon op het spoor': 'a trespassing incident',
            'een persoon op het spoor': 'a trespassing incident',
            'defect spoor': 'poor rail conditions',
            'een defect spoor': 'poor rail conditions',
            'defect aan het spoor': 'poor rail conditions',
            'een defect aan het spoor': 'poor rail conditions',
            'gladde sporen': 'slippery rail',
            'defecte bovenleiding': 'overhead wire problems',
            'een defecte bovenleiding': 'overhead wire problems',
            'versperring': 'an obstruction on the line',
            'een versperring': 'an obstruction on the line',
            'beperkingen op last van de politie': 'restrictions imposed by the police',
            'beperkingen op last van de brandweer': 'restrictions imposed by the fire brigade',
            'stroomstoring': 'power disruption',
            'een stroomstoring': 'power disruption',
            'bermbrand': 'a lineside fire'
        }

        if self.oorzaak_lang in vertalingen:
            return vertalingen[self.oorzaak_lang]
        else:
            return None

class ReisTip:
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
                return 'Non-stop tot %s' % self.stations_str(taal)
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

class InstapTip:
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

class OverstapTip:
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
