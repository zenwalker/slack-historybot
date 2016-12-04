from configparser import ConfigParser
import os


def get_config():
    filepath = os.environ['CONFIG_FILE']

    if not os.path.isfile(filepath):
        raise Exception('Config file not found ' + filepath)

    config = ConfigParser()
    config.read(filepath)
    return config


def truncate(text, max_length):
    if len(text) > max_length:
        return text[:max_length] + '...'
    return text
