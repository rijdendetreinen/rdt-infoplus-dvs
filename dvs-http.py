import cPickle as pickle
import zmq
import argparse
import isodate

#from bottle import route, run, debug
import bottle

import infoplus_dvs

# Default config (tijdelijk)
dvs_client_server = "tcp://46.19.34.170:8120"

# Maak verbinding
context = zmq.Context()
client = context.socket(zmq.REQ)
client.connect(dvs_client_server)

@bottle.route('/station/<station>')
def index(station):
	client.send('station/%s' % station)
	treinen = client.recv_pyobj()

	treinen_dict = {}

	# Lees trein array uit:
	if treinen != None:
		# Bepaal sortering adhv GET-parameter sorteer=
		if bottle.request.query.get('sorteer') == 'actueel':
			# Sorteer op geplande vertrektijd
			treinenSorted = sorted(treinen, key=lambda trein: treinen[trein].vertrekActueel)
		elif bottle.request.query.get('sorteer') == 'vertraging':
			# Sorteer op vertraging (hoog naar laag)
			treinenSorted = sorted(treinen, key=lambda trein: treinen[trein].vertraging)[::-1]
		else:
			# (Standaard) Sorteer op gepland vertrek
			treinenSorted = sorted(treinen, key=lambda trein: treinen[trein].vertrek)

		vertrektijden = []

		for treinNr in treinenSorted:
			trein = treinen[treinNr]

			trein_dict = { }
			trein_dict['treinNr'] = trein.treinNr
			trein_dict['vertrek'] = trein.lokaalVertrek().isoformat()
			trein_dict['bestemming'] = '/'.join(bestemming.langeNaam for bestemming in trein.eindbestemming)
			trein_dict['soort'] = trein.soort
			trein_dict['soortAfk'] = trein.soortCode
			trein_dict['vertraging'] = round(trein.vertraging.seconds / 60)
			trein_dict['spoor'] = '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel)
			if '/'.join(str(spoor) for spoor in trein.vertrekSpoor) != '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel):
				trein_dict['sprWijziging'] = True
			else:
				trein_dict['sprWijziging'] = False

			trein_dict['opmerkingen'] = trein.tips()

			# Todo:
			trein_dict['via'] = None
			trein_dict['opgeheven'] = False

			vertrektijden.append(trein_dict)

		return { 'status': 'OK', 'vertrektijden': vertrektijden }
	else:
		return { 'result': 'OK', 'vertrektijden': [] }

bottle.debug(True)

bottle.run(host='localhost', port=8080, reloader=True)

client.close()
context.term()