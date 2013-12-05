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
    treinNode = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Trein')

    # Maak trein object:
    trein = Trein()
    
    # Metadata over rit:
    trein.ritID = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitId').text
    trein.ritDatum = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitDatum').text
    trein.ritStation = parse_station(vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitStation'))
    trein.ritTimestamp = product.attrib.get('TimeStamp')
    
    # Treinnummer, soort/formule, etc:
    trein.treinNr = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinNummer').text
    trein.soort = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').text
    trein.soortCode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').attrib['Code']
    trein.vervoerder = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Vervoerder').text

    # Status:
    trein.status = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinStatus').text

    # Vertrektijd en vertraging:
    trein.vertrek = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Gepland"]').text)
    trein.vertrekActueel = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Actueel"]').text)

    trein.vertraging = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ExacteVertrekVertraging').text)
    trein.vertragingGedempt = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}GedempteVertrekVertraging').text)

    # Gepland en actueel vertrekspoor:
    trein.vertrekSpoor = parse_vertreksporen(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Gepland"]'))
    trein.vertrekSpoorActueel = parse_vertreksporen(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Actueel"]'))

    # Geplande en actuele bestemming:
    trein.eindbestemming = parse_stations(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Gepland"]'))
    trein.eindbestemmingActueel = parse_stations(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Actueel"]'))

    # Diverse statusvariabelen:
    trein.reserveren = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Reserveren').text)
    trein.toeslag = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Toeslag').text)
    ninNode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}NietInstappen')

    if ninNode != None:
        trein.nietInstappen = parse_boolean(ninNode.text)
    else:
        __logger__.warn("Element NietInstappen ontbreekt (trein %s/%s)", trein.treinNr, trein.ritStation.code)

    trein.rangeerBeweging = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RangeerBeweging').text)
    trein.speciaalKaartje = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpeciaalKaartje').text)
    trein.achterBlijvenAchtersteTreinDeel = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}AchterBlijvenAchtersteTreinDeel').text)

    # Parse wijzigingsberichten:
    trein.wijzigingen = []
    for wijzigingNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}Wijziging'):
        trein.wijzigingen.append(parse_wijziging(wijzigingNode))

    # Reistips:
    trein.reisTips = []
    for reisTipNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTip'):
        reisTip = ReisTip(reisTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTipCode').text)

        reisTip.stations = parse_stations(reisTipNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisTipStation'))
        trein.reisTips.append(reisTip)

    # Instaptips:
    trein.instapTips = []
    for instapTipNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTip'):
        instapTip = InstapTip()

        instapTip.uitstapStation = parse_station(instapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipUitstapStation'))
        instapTip.eindbestemming = parse_station(instapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipTreinEindBestemming'))
        instapTip.treinSoort = instapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipTreinSoort').text
        instapTip.instapSpoor = parse_spoor(instapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipVertrekSpoor'))
        instapTip.instapVertrek = isodate.parse_datetime(instapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}InstapTipVertrekTijd').text)

        trein.instapTips.append(instapTip)

    # Overstaptips:
    trein.overstapTips = []
    for overstapTipNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTip'):
        overstapTip = OverstapTip()

        overstapTip.bestemming = parse_station(overstapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTipBestemming'))
        overstapTip.overstapStation = parse_station(overstapTipNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}OverstapTipOverstapStation'))

        trein.overstapTips.append(overstapTip)

    # Verkorte route
    trein.verkorteRoute = []
    trein.verkorteRouteActueel = []

    trein.verkorteRoute = parse_stations(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}VerkorteRoute[@InfoStatus="Gepland"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))
    trein.verkorteRouteActueel = parse_stations(treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}VerkorteRoute[@InfoStatus="Actueel"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))

    # Parse treinvleugels
    trein.vleugels = []

    for vleugelNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugel'):
        vleugel_eindbestemming = parse_station(vleugelNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelEindBestemming[@InfoStatus="Gepland"]'))
        vleugel = TreinVleugel(vleugel_eindbestemming)

        # Vertrekspoor en bestemming voor de vleugel:
        vleugel.vertrekSpoor = parse_vertreksporen(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Gepland"]'))
        vleugel.vertrekSpoorActueel = parse_vertreksporen(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Actueel"]'))
        vleugel.eindbestemmingActueel = parse_station(vleugelNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelEindBestemming[@InfoStatus="Actueel"]'))

        # Stopstations:
        vleugel.stopstations = parse_stations(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}StopStations[@InfoStatus="Gepland"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))
        vleugel.stopstationsActueel = parse_stations(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}StopStations[@InfoStatus="Actueel"]/{urn:ndov:cdm:trein:reisinformatie:data:2}Station'))

        # Materieel per vleugel:
        vleugel.materieel = []
        for matNode in vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelDVS'):
            mat = Materieel()
            mat.soort = matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelSoort').text
            mat.aanduiding = matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelAanduiding').text
            mat.lengte = matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelLengte').text
            mat.eindbestemming = parse_station(matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelEindBestemming[@InfoStatus="Gepland"]'))
            mat.eindbestemmingActueel = parse_station(matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelEindBestemming[@InfoStatus="Actueel"]'))

            vertrekPositieNode = matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelVertrekPositie')
            if vertrekPositieNode != None:
                mat.vertrekPositie = vertrekPositieNode.text

            volgordeVertrekNode = matNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MaterieelDeelVolgordeVertrek')
            if volgordeVertrekNode != None:
                mat.volgordeVertrek = volgordeVertrekNode.text

            vleugel.materieel.append(mat)

        # Wijzigingsbericht(en):
        vleugel.wijzigingen = []
        for wijzigingNode in vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}Wijziging'):
            vleugel.wijzigingen.append(parse_wijziging(wijzigingNode))

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

    ritID = None
    ritStation = None
    ritDatum = None
    ritTimestamp = None

    treinNr = None
    eindbestemming = []
    eindbestemmingActueel = []

    status = 0

    soort = None
    soortCode = None
    
    vertrek = None
    vertrekActueel = None
    
    vertraging = None
    vertragingGedempt = None

    vertrekSpoor = []
    vertrekSpoorActueel = []

    reserveren = False
    toeslag = False
    nietInstappen = False
    speciaalKaartje = False
    rangeerBeweging = False
    achterBlijvenAchtersteTreinDeel = False

    verkorteRoute = []
    verkorteRouteActueel = []

    vleugels = []
    wijzigingen = []
    reisTips = []
    instapTips = []
    overstapTips = []

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
        return self.vertrekActueel.astimezone(tijdzone)

    def is_gewijzigd_vertrekspoor(self):
        """
        Geeft True terug indien het vertrekspoor gewijzigd is.
        """

        return (self.vertrekSpoor != self.vertrekSpoorActueel)

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

        for tip in self.reisTips:
            tips.append(tip.to_str(taal))
        for tip in self.instapTips:
            tips.append(tip.to_str(taal))
        for tip in self.overstapTips:
            tips.append(tip.to_str(taal))

        if self.nietInstappen == True:
            tips.append(self.niet_instappen_str(taal))

        if self.achterBlijvenAchtersteTreinDeel == True:
            tips.append(self.achterblijven_str(taal))

        if self.speciaalKaartje == True:
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

        if self.nietInstappen == True:
            if taal == 'en':
                return 'Do not board'
            else:
                return 'Niet instappen'

    def speciaal_kaartje_str(self, taal):
        """
        Geef een tekstmelding terug als voor deze trein een speciaal kaartje
        vereist is.
        """

        if self.speciaalKaartje == True:
            if taal == 'en':
                return 'Special ticket required'
            else:
                return 'Bijzonder ticket'

    def achterblijven_str(self, taal):
        """
        Geef een tekstmelding terug als het achterste treindeel achterblijft.
        """

        if self.achterBlijvenAchtersteTreinDeel == True:
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
        (self.soortCode, self.ritID, self.lokaal_vertrek(),
            self.vertraging, self.ritStation.code, self.vertrekSpoorActueel,
            self.eindbestemmingActueel)


class TreinVleugel: 
    """
    Een treinvleugel is een deel van de trein met een bepaalde eindbestemming,
    materieel en wijzigingen. Een trein kan uit meerdere vleugels bestaan met
    verschillende bestemmingen.
    """

    vertrekSpoor = []
    vertrekSpoorActueel = []
    eindbestemming = None
    eindbestemmingActueel = None
    stopstations = []
    stopstationsActueel = []
    materieel = []
    wijzigingen = []

    def __init__(self, eindbestemming):
        self.eindbestemming = eindbestemming
        self.eindbestemmingActueel = eindbestemming


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
    eindbestemmingActueel = None
    vertrekPositie = None
    volgordeVertrek = None

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
                return 'Delayed'
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
                    '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel)
                else:
                    return 'Spoorwijziging, vertrekt van spoor %s' % \
                    '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel)
        elif self.wijziging_type == '22':
            if taal == 'en':
                return 'Platform has been allocated'
            else:
                return 'Vertrekspoor toegewezen'
        elif self.wijziging_type == '30':
            if taal == 'en':
                return 'Schedule changed'
            else:
                return 'Gewijzigde dienstregeling'
        elif self.wijziging_type == '31':
            if taal == 'en':
                return 'Additional train'
            else:
                return 'Extra trein'
        elif self.wijziging_type == '32':
            if taal == 'en':
                return 'Train is cancelled'
            else:
                return 'Trein rijdt niet%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '33':
            if taal == 'en':
                return 'Diverted train'
            else:
                return 'Rijdt via een andere route%s' % self.oorzaak_prefix(taal)
        elif self.wijziging_type == '34':
            if taal == 'en':
                return 'Terminates at %s' % self.station.lange_naam
            else:
                return 'Rijdt niet verder dan %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
        elif self.wijziging_type == '35':
            if taal == 'en':
                return 'Continues to %s' % self.station.lange_naam
            else:
                return 'Rijdt verder naar %s%s' % (self.station.lange_naam, self.oorzaak_prefix(taal))
        elif self.wijziging_type == '41':
            if taal == 'en':
                return 'Attention, train goes to %s' % self.station.lange_naam
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

        if taal == 'en' or self.oorzaak_lang == None:
            return ''
        else:
            return ' i.v.m. %s' % self.oorzaak_lang

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

    treinSoort = None
    treinSoortCode = None
    uitstapStation = None
    eindbestemming = None
    instapVertrek = None
    instapSpoor = None

    def __init__(self):
        pass

    def to_str(self, taal='nl'):
        """
        Vertaal de instaptip naar een concreet bericht (string)
        in de gegeven taal.
        """

        if taal == 'en':
            return 'The %s to %s reaches %s sooner' % (self.treinSoort,
                self.eindbestemming.lange_naam, self.uitstapStation.lange_naam)
        else:
            return 'De %s naar %s is eerder in %s' % (self.treinSoort,
                self.eindbestemming.lange_naam, self.uitstapStation.lange_naam)

class OverstapTip:
    """
    Class om overstaptips te bewaren. Een overstaptip is een tip dat om een
    bepaalde bestemming te bereiken op een overstapstation moet worden
    overgestapt.
    """

    bestemming = None
    overstapStation = None

    def __init__(self):
        pass

    def to_str(self, taal='nl'):
        """
        Vertaal de overstaptip naar een concreet bericht (string)
        in de gegeven taal.
        """

        if taal == 'en':
            return 'For %s, change at %s' % (self.bestemming.lange_naam,
                self.overstapStation.lange_naam)
        else:
            return 'Voor %s overstappen in %s' % (self.bestemming.lange_naam,
                self.overstapStation.lange_naam)


class OngeldigDvsBericht(Exception):
    """
    Exception voor ongeldige DVS berichten
    """

    # Verder een standaard Exception

    pass