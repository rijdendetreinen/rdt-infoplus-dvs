import xml.etree.ElementTree as ET
import isodate
import pytz

def parse_trein(data):
	# Parse XML:
	root = ET.fromstring(data)

	product = root.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ReisInformatieProductDVS')
	vertrekstaat = product.find('{urn:ndov:cdm:trein:reisinformatie:data:2}DynamischeVertrekStaat')
	treinNode = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}Trein')

	print product.attrib.get('TimeStamp'),

	ritID = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitId').text
	ritDatum = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitDatum').text
	ritStation = vertrekstaat.find('{urn:ndov:cdm:trein:reisinformatie:data:2}RitStation')
	ritStationCode = ritStation.find('{urn:ndov:cdm:trein:reisinformatie:data:2}StationCode').text
	
	bestemmingPlanNode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Gepland"]')
	bestemmingActueelNode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinEindBestemming[@InfoStatus="Actueel"]')
	
	bestemmingPlan = parse_station(bestemmingPlanNode)
	bestemmingActueel = parse_station(bestemmingActueelNode)

	# Maak trein object
	trein = vertrektrein()
	trein.ritID = ritID
	trein.ritDatum = ritDatum
	trein.ritStationCode = ritStationCode
	
	trein.treinNr = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinNummer').text
	trein.soort = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').text
	trein.soortCode = treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinSoort').attrib['Code']

	trein.eindbestemmingPlan = bestemmingPlan
	trein.eindbestemming = bestemmingActueel

	trein.vertrek = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Gepland"]').text)
	trein.vertrekActueel = isodate.parse_datetime(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}VertrekTijd[@InfoStatus="Actueel"]').text)

	trein.vertraging = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}ExacteVertrekVertraging').text)
	trein.vertragingGedempt = isodate.parse_duration(treinNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}GedempteVertrekVertraging').text)

	trein.vertrekSpoor = []
	trein.vertrekSpoorActueel = []

	for spoorNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Gepland"]'):
		trein.vertrekSpoor.append(spoorNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text)
	for spoorNode in treinNode.findall('{urn:ndov:cdm:trein:reisinformatie:data:2}TreinVertrekSpoor[@InfoStatus="Actueel"]'):
		trein.vertrekSpoorActueel.append(spoorNode.find('{urn:ndov:cdm:trein:reisinformatie:data:2}SpoorNummer').text)

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
	ritStationCode = None
	ritDatum = None

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

	def __repr__(self):
		est = pytz.timezone('Europe/Amsterdam')
		vertrektijd = self.vertrek.astimezone(est)
		return '<trein %-3s %6s om %s +%s spr %s van %-4s naar %s>' % (self.soortCode, self.ritID, vertrektijd, self.vertraging, self.vertrekSpoorActueel, self.ritStationCode, self.eindbestemming)