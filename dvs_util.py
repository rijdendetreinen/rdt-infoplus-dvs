"""
Generieke utility functies.
"""

import os
import sys
import yaml
import logging
import logging.config


def load_config(config_file_path='config/config.yaml'):
    """
    Setup logging configuration
    """

    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r') as config_file:
                config = yaml.load(config_file.read())
        except (yaml.parser.ParserError, yaml.parser.ScannerError) as exception:
            print "YAML fout in config file: %s" % exception
            sys.exit(1)
        except Exception as exception:
            print "Fout in configuratiebestand. Foutmelding: %s" % exception
            sys.exit(1)
    else:
        print "Configuratiebestand '%s' niet aanwezig" % config_file_path
        sys.exit(1)

    return config


def setup_logging(config):
    """
    Setup logging configuration
    """

    # Check of er een logger configuratie is opgegeven:
    if 'logging' in config and 'log_config' in config['logging']:
        log_config_file = config['logging']['log_config']
    
        # Stel logger in adhv config:
        if os.path.exists(log_config_file):
            with open(log_config_file, 'r') as config_file:
                log_config = yaml.load(config_file.read())
            logging.config.dictConfig(log_config)
            return

    logging.basicConfig(level=logging.INFO)
