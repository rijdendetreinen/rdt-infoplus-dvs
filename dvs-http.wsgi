import os, sys
sys.path.insert(0,os.path.dirname(__file__))

import bottle
import dvs_http_interface

# Default config:
dvs_http_interface.dvs_client_server = "tcp://127.0.0.1:8120"

application = bottle.default_app()