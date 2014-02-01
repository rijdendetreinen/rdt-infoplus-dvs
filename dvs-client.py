import cPickle as pickle
import zmq
import argparse

import infoplus_dvs

# Default config (tijdelijk)
dvs_client_server = "tcp://127.0.0.1:8120"

# Initialiseer argparse
parser = argparse.ArgumentParser(description='RDT InfoPlus DVS client')
parser.add_argument('STATIONCODE', action='store', help='Station (code) waarvoor treinen getoond moeten worden')
args = parser.parse_args()

station = args.STATIONCODE

# Maak verbinding
context = zmq.Context()
client = context.socket(zmq.REQ)
client.connect(dvs_client_server)
client.send('station/%s' % station)
treinen = client.recv_pyobj()

# Lees trein array uit:
if treinen != None:
	print "Treinen vanaf station %s:" % station.upper()
	print "-" * 70

	# Sorteer op geplande vertrektijd
	treinenSorted = sorted(treinen, key=lambda trein: treinen[trein].vertrek)

	for treinNr in treinenSorted:
		trein = treinen[treinNr]

		print "%s (%s)  +%s  %-10s %6s  naar " % (trein.lokaal_vertrek().strftime("%H:%M"), trein.lokaal_vertrek_actueel().strftime("%H:%M"), trein.vertraging, trein.soort, trein.treinnr),
		print '/'.join(bestemming.lange_naam for bestemming in trein.eindbestemming)

		for vleugel in trein.vleugels:
			if (len(trein.vleugels) > 1):
				print "                         * %s" % vleugel.eindbestemming.lange_naam
			print "                           via: ",
			print ', '.join(station.lange_naam for station in vleugel.stopstations)

			print "                           mat: ",
			print ', '.join(mat.soort + ' ' + mat.aanduiding for mat in vleugel.materieel)
else:
	print "Geen treinen"