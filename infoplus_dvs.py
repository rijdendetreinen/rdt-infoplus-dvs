import xml.etree.ElementTree as ET
import isodate
import pytz

def parse_trein(data):
	# Parse XML:
	root = ET.fromstring(data)

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
	trein.nietInstappen = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}NietInstappen').text)
	trein.rangeerBeweging = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RangeerBeweging').text)
	trein.speciaalKaartje = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpeciaalKaartje').text)
	trein.achterBlijvenAchtersteTreinDeel = parse_boolean(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}AchterBlijvenAchtersteTreinDeel').text)

	# Parse wijzigingsberichten:
	for wijzigingNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}Wijziging'):
		trein.wijzigingen.append(parse_wijziging(wijzigingNode))

	# TODO: verkorte route, reistips

	# Parse treinvleugels
	trein.vleugels = []

	for vleugelNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugel'):
		vleugel = TreinVleugel()

		# Vertrekspoor en bestemming voor de vleugel:
		vleugel.vertrekSpoor = parse_vertreksporen(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Gepland"]'))
		vleugel.vertrekSpoorActueel = parse_vertreksporen(vleugelNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelVertrekSpoor[@InfoStatus="Actueel"]'))
		vleugel.eindbestemming = parse_station(vleugelNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVleugelEindBestemming[@InfoStatus="Gepland"]'))
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


def parse_stations(stationsNode):
	stations = []
	for stationNode in stationsNode:
		stations.append(parse_station(stationNode))

	return stations


def parse_station(stationElement):
	station_object = Station()
	station_object.code = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}StationCode').text
	station_object.korteNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}KorteNaam').text
	station_object.middelNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MiddelNaam').text
	station_object.langeNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}LangeNaam').text
	station_object.uic = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}UICCode').text
	station_object.type = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Type').text

	return station_object


def parse_wijziging(wijzigingNode):
	wijziging = Wijziging()
	wijziging.type = wijzigingNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingType').text
	
	oorzaakNode = wijzigingNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingOorzaakKort')
	if oorzaakNode != None:
		wijziging.oorzaak = oorzaakNode.text
	
	oorzaakLangNode = wijzigingNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingOorzaakLang')
	if oorzaakLangNode != None:
		wijziging.oorzaakLang = oorzaakLangNode.text

	stationNode = wijzigingNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}WijzigingStation')
	if stationNode != None:
		wijziging.station = parse_station(stationNode)

	return wijziging


def parse_vertreksporen(sporenNode):
	sporen = []
	for spoorNode in sporenNode:
		sporen.append(parse_spoor(spoorNode))

	return sporen


def parse_spoor(spoorElement):
	spoor = Spoor()
	
	spoor.nummer = spoorElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text
	faseNode = spoorElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorFase')
	if (faseNode != None):
		spoor.fase = faseNode.text

	return spoor


def parse_boolean(value):
	if value == 'J':
		return True
	else:
		return False

class Station:
	code = None
	korteNaam = None
	middelNaam = None
	langeNaam = None
	uic = None
	type = None

	def __repr__(self):
		return '<station %s %s>' % (self.code, self.langeNaam)


class Spoor:
	nummer = None
	fase = None

	def __repr__(self):
		if self.fase == None:
			return self.nummer
		else:
			return '%s%s' % (self.nummer, self.fase)

		return spoor

class Trein:
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

	vleugels = []
	wijzigingen = []

	def lokaalVertrek(self):
		tz = pytz.timezone('Europe/Amsterdam')
		return self.vertrek.astimezone(tz)

	def lokaalVertrekActueel(self):
		tz = pytz.timezone('Europe/Amsterdam')
		return self.vertrekActueel.astimezone(tz)

	def gewijzigdVertrekspoor(self):
		return (self.vertrekSpoor != self.vertrekSpoorActueel)

	def __repr__(self):
		return '<Trein %-3s %6s v%s +%s %-4s %-3s -- %-4s>' % (self.soortCode, self.ritID, self.lokaalVertrek(), self.vertraging, self.ritStation.code, self.vertrekSpoorActueel, self.eindbestemmingActueel)


class TreinVleugel:
	vertrekSpoor = []
	vertrekSpoorActueel = []
	eindbestemming = None
	eindbestemmingActueel = None
	stopstations = []
	stopstationsActueel = []
	materieel = []
	wijzigingen = []


class Materieel:
	soort = None
	aanduiding = None
	lengte = 0
	eindbestemming = None
	eindbestemmingActueel = None
	vertrekPositie = None
	volgordeVertrek = None

	def treintype(self):
		if self.aanduiding != None:
			return '%s-%s' % (self.soort, self.aanduiding)
		else:
			return self.soort

class Wijziging:
	type = 0
	oorzaak = None
	oorzaakLang = None
	station = None