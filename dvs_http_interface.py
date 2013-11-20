import cPickle as pickle
import zmq
import argparse
import isodate
import bottle

import infoplus_dvs


@bottle.route('/station/<station>')
def index(station):
	# Maak verbinding
	context = zmq.Context()
	client = context.socket(zmq.REQ)
	client.connect(dvs_client_server)

	# Stuur opdracht:
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

			# Basis treininformatie
			trein_dict['treinNr'] = trein.treinNr
			trein_dict['vertrek'] = trein.lokaalVertrek().isoformat()
			trein_dict['bestemming'] = '/'.join(bestemming.langeNaam for bestemming in trein.eindbestemmingActueel)
			trein_dict['soort'] = trein.soort
			trein_dict['soortAfk'] = trein.soortCode
			trein_dict['vertraging'] = round(trein.vertraging.seconds / 60)
			trein_dict['spoor'] = '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel)

			if '/'.join(str(spoor) for spoor in trein.vertrekSpoor) != '/'.join(str(spoor) for spoor in trein.vertrekSpoorActueel):
				trein_dict['sprWijziging'] = True
			else:
				trein_dict['sprWijziging'] = False

			trein_dict['opmerkingen'] = trein.wijzigingen_str('nl')
			trein_dict['tips'] = trein.tips('nl')
			trein_dict['opgeheven'] = False
			trein_dict['status'] = trein.status

			# Trein opgeheven: wis spoor, vertraging etc.
			if trein.is_opgeheven():
				trein_dict['opgeheven'] = True
				trein_dict['spoor'] = None
				trein_dict['vertraging'] = 0

			# Verkorte (via)-route
			if trein.verkorteRouteActueel == None or len(trein.verkorteRouteActueel) == 0:
				trein_dict['via'] = None
			else:
				trein_dict['via'] = ', '.join(via.middelNaam for via in trein.verkorteRouteActueel)

			# Treinvleugels:
			trein_dict['vleugels'] = []
			for vleugel in trein.vleugels:
				vleugel_dict = { 'bestemming': vleugel.eindbestemmingActueel.langeNaam }
				vleugel_dict['mat'] = [mat.treintype() for mat in vleugel.materieel]

				trein_dict['vleugels'].append(vleugel_dict)

			vertrektijden.append(trein_dict)

		return { 'result': 'OK', 'vertrektijden': vertrektijden }
	else:
		return { 'result': 'OK', 'vertrektijden': [] }

	client.close()
	context.term()
