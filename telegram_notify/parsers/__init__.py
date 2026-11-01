from . import marukyu

PARSERS = {"marukyu": marukyu.parse_list}


def get_parser(name):
    return PARSERS[name]
