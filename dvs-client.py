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

		print "%s (%s)  +%s  %-10s %6s  naar " % (trein.lokaalVertrek().strftime("%H:%M"), trein.lokaalVertrekActueel().strftime("%H:%M"), trein.vertraging, trein.soort, trein.treinNr),
		for bestemming in trein.eindbestemming:
			print bestemming.langeNaam,
		print

		for vleugel in trein.vleugels:
			if (len(trein.vleugels) > 1):
				print "                         * %s" % vleugel.eindbestemming.langeNaam
			print "                           via: ",
			for station in vleugel.stopstations:
				print station.middelNaam,
			print
			print "                           mat: ",
			for mat in vleugel.materieel:
				print mat.soort, mat.aanduiding, " ",
			print
else:
	print "Geen treinen"