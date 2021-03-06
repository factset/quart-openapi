"""typing.py

Provide type definitions for use in other modules
"""

from typing import Union, Tuple, Iterable, Dict, Any, Type
from jsonschema import Draft3Validator, Draft4Validator, Draft6Validator, Draft7Validator

from .marshmallow import MARSHMALLOW, Schema

PyTypes = Union[Type[int], Type[float], Type[str], Type[bool]]

if MARSHMALLOW:
    ValidatorType = Union[PyTypes, str, Draft3Validator, Draft4Validator, Draft6Validator, Draft7Validator, Schema]
else:
    ValidatorType = Union[PyTypes, str, Draft3Validator, Draft4Validator, Draft6Validator, Draft7Validator]

ValidatorTypes = Union[ValidatorType, Iterable['ValidatorType']]
ExpectedDescList = Union[ValidatorTypes, Tuple[ValidatorTypes], Tuple[ValidatorTypes, str],
                         Tuple[ValidatorTypes, str, Dict[str, Any]]]
HeaderType = Union[ValidatorType, Iterable[PyTypes], Dict[str, Any]]
