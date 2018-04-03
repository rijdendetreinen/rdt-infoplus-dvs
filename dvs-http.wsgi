import os, sys
sys.path.insert(0,os.path.dirname(__file__))

import bottle
import dvs_util
import dvs_http_interface

# Load config:
configfile = sys.argv[1]
# Gunicorn ondersteund geen parameters, gebruik dan de standaard config file.
if 'gunicorn' in sys.argv[0]:
    configfile = 'config/http.yaml'
dvs_http_interface.config = dvs_util.load_config(configfile)
dvs_util.setup_logging(dvs_http_interface.config)

application = bottle.default_app()