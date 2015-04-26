import os, sys
sys.path.insert(0,os.path.dirname(__file__))

import bottle
import dvs_util
import dvs_http_interface

# Load config:
dvs_http_interface.config = dvs_util.load_config(sys.argv[1])
dvs_util.setup_logging(dvs_http_interface.config)

application = bottle.default_app()