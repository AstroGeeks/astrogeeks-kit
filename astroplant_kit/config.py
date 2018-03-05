import json

def read_config():
    """
    Read the configuration file at 'astroplant_kit/kit_config.json'.

    :return: The json configuration as a dictionary.
    """
    with open('astroplant_kit/kit_config.json') as f:
        data = json.load(f)

    return data
