from copy import deepcopy
from itertools import filterfalse
from inspect import getdoc
import re

RE_RAISES = re.compile(r'^:raises\s+(?P<name>[\w\d_]+)\s*:\s*(?P<description>.*)$', re.MULTILINE)
RE_URL = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')
FIRST_CAP_RE = re.compile('(.)([A-Z][a-z]+)')
ALL_CAP_RE = re.compile('([a-z0-9])([A-Z])')

def parse_docstring(obj):
    raw = getdoc(obj)
    summary = raw.strip(' \n').split('\n')[0].split('.')[0] if raw else None
    raises = {}
    details = raw.replace(summary, '').lstrip('. \n').strip(' \n') if raw else None
    for match in RE_RAISES.finditer(raw or ''):
        raises[match.group('name')] = match.group('description')
        if details:
            details = details.replace(match.group(0), '')
    parsed = {
        'raw': raw,
        'summary': summary or None,
        'details': details or None,
        'returns': None,
        'params': [],
        'raises': raises
    }
    return parsed


class cached_property(object):
    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value

def extract_path(path):
    return RE_URL.sub(r'{\1}', path)

def not_none(data):
    return dict(filterfalse(lambda x: x[1] is None, data.items()))

def camel_to_snake(name):
    s1 = FIRST_CAP_RE.sub(r'\1_\2', name)
    return ALL_CAP_RE.sub(r'\1_\2', s1).lower()

def merge(first, second):
    if not isinstance(second, dict):
        return second
    result = deepcopy(first)
    for key, value in second.items():
        if key in result and isinstance(result[key], dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
