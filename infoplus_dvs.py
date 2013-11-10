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
	trein = vertrektrein()
	
	# Metadata over rit:
	trein.ritID = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitId').text
	trein.ritDatum = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitDatum').text
	trein.ritStation = parse_station(vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitStation'))
	trein.ritTimestamp = product.attrib.get('TimeStamp')
	
	# Treinnummer, soort/formule, etc:
	trein.treinNr = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinNummer').text
	trein.soort = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').text
	trein.soortCode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').attrib['Code']

	# Vertrektijd en vertraging:
	trein.vertrek = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Gepland"]').text)
	trein.vertrekActueel = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Actueel"]').text)

	trein.vertraging = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ExacteVertrekVertraging').text)
	trein.vertragingGedempt = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}GedempteVertrekVertraging').text)

	# Gepland en actueel vertrekspoor:
	trein.vertrekSpoor = []
	trein.vertrekSpoorActueel = []

	for spoorNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Gepland"]'):
		trein.vertrekSpoor.append(spoorNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text)
	for spoorNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Actueel"]'):
		trein.vertrekSpoorActueel.append(spoorNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text)

	# Geplande en actuele bestemming:
	trein.eindbestemmingPlan = parse_station(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Gepland"]'))
	trein.eindbestemming = parse_station(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Actueel"]'))

	return trein

def parse_station(stationElement):
	station_object = station()
	station_object.code = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}StationCode').text
	station_object.korteNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}KorteNaam').text
	station_object.middelNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}MiddelNaam').text
	station_object.langeNaam = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}LangeNaam').text
	station_object.uic = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}UICCode').text
	station_object.type = stationElement.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Type').text

	return station_object


class station:
	code = None
	korteNaam = None
	middelNaam = None
	langeNaam = None
	uic = None
	type = None

	def __repr__(self):
		return '<station %s %s>' % (self.code, self.langeNaam)


class vertrektrein:
	ritID = None
	ritStation = None
	ritDatum = None
	ritTimestamp = None

	treinNr = None
	eindbestemming = None
	eindbestemmingActueel = None

	soort = None
	soortCode = None
	
	vertrek = None
	vertrekActueel = None
	
	vertraging = None
	vertragingGedempt = None

	vertrekSpoor = []
	vertrekSpoorActueel = []

	def lokaalVertrek(self):
		tz = pytz.timezone('Europe/Amsterdam')
		return self.vertrek.astimezone(tz)

	def lokaalVertrekActueel(self):
		tz = pytz.timezone('Europe/Amsterdam')
		return self.vertrekActueel.astimezone(tz)

	def gewijzigdVertrekspoor(self):
		return (self.vertrekSpoor != self.vertrekSpoorActueel)

	def __repr__(self):
		return '<trein %-3s %6s v%s +%s %-4s %-3s -- %-4s>' % (self.soortCode, self.ritID, self.lokaalVertrek(), self.vertraging, self.ritStation.code, '-'.join(self.vertrekSpoorActueel), self.eindbestemming.code)