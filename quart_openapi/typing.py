from typing import Union, Tuple, Iterable, Dict, Any, Type
from jsonschema import Draft4Validator

PyTypes = Union[Type[int], Type[float], Type[str], Type[bool]]
ValidatorType = Union[PyTypes, str, Draft4Validator]
ValidatorTypes = Union[ValidatorType, Iterable['ValidatorType']]
ExpectedDescList = Union[ValidatorTypes, Tuple[ValidatorTypes], Tuple[ValidatorTypes, str],
                         Tuple[ValidatorTypes, str, Dict[str, Any]]]
HeaderType = Union[PyTypes, str, Iterable[PyTypes], Draft4Validator, Dict[str, Any]]
