#!/usr/bin/env python3

"""
Bootstraps the kit: sets up logging, creates the API client, and starts the kit run routine.
"""

# Make sure astroplant_kit is in the path
import os
import sys

import logging
from astroplant_client import Client
from .kit import Kit
from . import config

def main():
    init_logger()
    conf = read_config()
    init_client(conf)
    run_kit()

def init_logger():
    ## create logger
    logger = logging.getLogger("AstroPlant")
    logger.setLevel(logging.DEBUG)

    ## create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ## create formatter
    formatter = logging.Formatter('%(asctime)s - %(threadName)s - %(name)s - %(levelname)s - %(message)s')

    ## add formatter to console handler
    ch.setFormatter(formatter)

    ## add console handler to logger
    logger.addHandler(ch)

def read_config():
    logger = logging.getLogger("AstroPlant")
    logger.info('Reading configuration.')
    try:
        conf = config.read_config()
    except Exception as e:
        logger.error('Exception while reading configuration: %s' % e)
        sys.exit(e.errno)
    return conf

def init_client(conf):
    logger = logging.getLogger("AstroPlant")
    logger.info('Creating AstroPlant network client.')
    api_client = Client(conf["api"]["root"], conf["websockets"]["url"])

    logger.info('Authenticating AstroPlant network client.')
    api_client.authenticate(conf["auth"]["serial"], conf["auth"]["secret"])

def run_kit():
    logger = logging.getLogger("AstroPlant")
    logger.info('Initialising kit.')
    kit = Kit(api_client, conf["debug"])
    kit.run()

if __name__ == "__main__":
    main()
