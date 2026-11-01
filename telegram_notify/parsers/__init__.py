from . import marukyu

PARSERS = {"marukyu": marukyu}


def get_parser(name):
    return PARSERS[name]
