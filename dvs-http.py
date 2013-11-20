import bottle
import dvs_http_interface

# Default config (tijdelijk)
dvs_http_interface.dvs_client_server = "tcp://46.19.34.170:8120"

bottle.debug(True)
bottle.run(host='localhost', port=8080, reloader=True)