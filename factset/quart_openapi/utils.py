from copy import deepcopy
from itertools import filterfalse
from inspect import getdoc
import re
from typing import Dict, Union, List, Callable, Any, Type

#: regex for finding ':raises ...: ...' in a docstring
_RE_RAISES = re.compile(r'^:raises\s+(?P<name>[\w\d_]+)\s*:\s*(?P<description>.*)$', re.MULTILINE)
#: find the first capital letter of a camel cased string
_FIRST_CAP_RE = re.compile('(.)([A-Z][a-z]+)')
#: find the rest of the spots that go from lower case to Capital for camel case
_ALL_CAP_RE = re.compile('([a-z0-9])([A-Z])')
#: find the URL path params
_RE_URL = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')

def parse_docstring(obj: object) -> Dict[str, Union[str, List, Dict[str, str], None]]:
    """Split the docstring of an object into useful pieces

    :param obj: any object with a docstring
    :return: A dictionary containing the following

             * **raw:** the raw docstring
             * **summary:** The first sentence of the docstring
             * **details:** The docstring without the first sentence or any references to ':raises ...:'
             * **returns:** Currently `None`
             * **params:** Currently an empty `list`
             * **raises:** a dict mapping exception names to descriptions from the docstring that were
                           found via ':raises ...:'
    """
    raw = getdoc(obj)
    summary = raw.strip(' \n').split('\n')[0].split('.')[0] if raw else None
    raises = {}
    details = raw.replace(summary, '').lstrip('. \n').strip(' \n') if raw else None
    for match in _RE_RAISES.finditer(raw or ''):
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

def extract_path(path: str) -> str:
    """Transform the Quart/Flask/Werkzeug URL patterns to an openapi one

    :param path: the URL Pattern
    :return: the pattern in the openapi format for path params
    """
    return _RE_URL.sub(r'{\1}', path)

class cached_property(object):
    """A quick class to cache an object property produced by a function, to be used in place
    of `@property` if the function to return the value of a property is expensive. Currently
    used to cache the result of the OpenApi docs for serving quickly to '/openapi.json'.

    It will properly forward the docstring of the decorated function and cache the output of
    the property function after the first call to it.
    """

    def __init__(self, func: Callable) -> None:
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj: Type[object], cls: object) -> Any:
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value

def not_none(data: Dict[Any, Any]) -> Dict[Any, Any]:
    """Return the passed in dictionary after removing any keys whose value is `None`"""
    return dict(filterfalse(lambda x: x[1] is None, data.items()))

def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case """
    s1 = _FIRST_CAP_RE.sub(r'\1_\2', name)
    return _ALL_CAP_RE.sub(r'\1_\2', s1).lower()

def merge(first: Dict[Any, Any], second: Dict[Any, Any]) -> Dict[Any, Any]:
    """Utility function to merge the keys and values of two dicts recursively

    :param first: source dict to start with
    :param second: dict to merge in, any keys that appear in both will be overwritten from this one
    :return: The merged dictionary or `second` if it wasn't a dict

    If the second argument is not a :class:`dict` or a subtype of it, it is just returned. The
    first argument will be deep copied using :func:`~copy.deepcopy` and then the keys and values
    from second will be cursively `deepcopy`'d into it before returning.
    """
    if not isinstance(second, dict):
        return second
    result = deepcopy(first)
    for key, value in second.items():
        if key in result and isinstance(result[key], dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
