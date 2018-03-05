import os
import json

def read_config():
    """
    Read the configuration file at 'astroplant_kit/kit_config.json'.

    :return: The json configuration as a dictionary.
    """
    path = os.path.abspath('astroplant_kit/kit_config.json')
    with open(path) as f:
        data = json.load(f)

    return data
