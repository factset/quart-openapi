from quart.routing import ROUTE_VAR_RE, Map as RouteMap
from jsonschema import Draft4Validator
from itertools import chain
from collections import OrderedDict, Hashable
from http import HTTPStatus
from .pint import Pint
from .resource import Resource, get_expect_args
from .utils import parse_docstring, not_none, merge, extract_path
from .typing import ValidatorTypes, HeaderType
from typing import Dict, Any, Generator, Tuple, Union, Optional, Callable, Iterable, Mapping

DEFAULT_RESPONSE_DESCRIPTION = 'Success'
DEFAULT_RESPONSE = {'description': DEFAULT_RESPONSE_DESCRIPTION}
PY_TYPES = {
    int: 'integer',
    float: 'number',
    str: 'string',
    bool: 'boolean',
    None: 'void'
}

PATH_TYPES = {
    'int': 'integer',
    'float': 'number',
    'string': 'string',
    'default': 'string'
}

def _clean_header(header: HeaderType) -> Dict[str, Any]:
    """Convert headers to dict representation

    :param header: Either a header description, a type, a validator, or a dict of keys for the
                   header param object
    :return: The dict of properties for the given header param normalized to the openapi 3.0 spec
    """
    if isinstance(header, str):
        header = {'description': header}
    typedef = header.get('type', 'string')
    if isinstance(typedef, Hashable) and typedef in PY_TYPES:
        header['type'] = PY_TYPES[typedef]
    elif isinstance(typedef, (list, tuple)) and len(typedef) == 1 and typedef[0] in PY_TYPES:
        header['type'] = 'array'
        header['items'] = {'type': PY_TYPES[typedef[0]]}
    elif hasattr(typedef, '__schema__'):
        header.update(typedef.__schema__)
    else:
        header['type'] = typedef
    return not_none(header)

def _parse_rule(rule: str) -> Generator[Tuple[str,str], None, None]:
    """Generator for the converters for the path parameters

    :param rule: a route string
    :return: each iteration yields the next tuple of (converter name, variable name)
    """
    for match in ROUTE_VAR_RE.finditer(rule):
        named_groups = match.groupdict()
        yield (named_groups['converter'], named_groups['variable'])

def _extract_path_params(path: str) -> OrderedDict:
    """Generate the path params from the route

    :param path: The route string
    :return: An :class:`~collections.OrderedDict` of param names to definitions
    """
    params = OrderedDict()
    for converter, variable in _parse_rule(path):
        if not converter:
            continue
        param = {
            'name': variable,
            'in': 'path',
            'required': True,
            'schema': {}
        }

        if converter in PATH_TYPES:
            param['schema']['type'] = PATH_TYPES[converter]
        elif converter == 'uuid':
            param['schema']['type'] = 'string'
            param['schema']['format'] = 'uuid'
        elif converter in RouteMap.default_converters:
            param['schema']['type'] = 'string'
        else:
            raise ValueError('Unsupported type converter: %s' % converter)
        params[variable] = param
    return params

class Swagger(object):
    """Class for generating a openapi.json from the resources and information defined with
    :class:`~factset.swaggen.Pint`"""

    def __init__(self, api: Pint) -> None:
        """Construct a Swagger object for generating the openapi Json

        :param api: the main app interface for getting the base model and resources
        """
        self.api = api
        self._components = OrderedDict([('schemas', OrderedDict()),
                                        ('responses', OrderedDict()),
                                        ('parameters', OrderedDict()),
                                        ('examples', OrderedDict()),
                                        ('requestBodies', OrderedDict()),
                                        ('headers', OrderedDict()),
                                        ('securitySchemes', OrderedDict())])

    def as_dict(self) -> Dict[str, Any]:
        """Return a dict which can be used with the :mod:`json` module to return valid json"""
        infos = {
            'title': self.api.title or 'OpenApi Rest Documentation',
            'version': self.api.version or '1.0'
        }
        if self.api.description:
            infos['description'] = self.api.description
        if self.api.contact and (self.api.contact_email or self.api.contact_url):
            infos['contact'] = not_none({
                'name': self.api.contact,
                'email': self.api.contact_email,
                'url': self.api.contact_url
            })

        components = self.serialize_components() or None
        paths = {}
        for resource, path, methods in self.api.resources:
            paths[extract_path(path)] = self.serialize_resource(resource, path, methods)

        spec = {
            'openapi': '3.0.0',
            'info': infos,
            'servers': [
                {
                    'url': ''.join([self.api.config['PREFERRED_URL_SCHEME'], '://',
                                    self.api.config['SERVER_NAME'] or ''])
                }
            ],
            'paths': paths,
            'components': components
        }
        return not_none(spec)

    def register_component(self, category: str, name: str, schema: Dict[str, Any]) -> None:
        """Used for populating the components_ section of the openapi docs

        :param category: The category under the component section
        :param name: The name of the model for reference
        :param schema: the actual schema for this object
        """
        if category not in self._components:
            raise ValueError('invalid category for components')
        self._components[category][name] = schema

    def serialize_components(self) -> Mapping[str, Dict[str, Any]]:
        """Generate the json for the components_ section

        :return: An :class:`~collections.OrderedDict` of the components
        """
        if self.api.base_model is None:
            return {}
        base_components = self.api.base_model.resolve('#/components')[1]
        for category, val in base_components.items():
            for name, schema in val.items():
                self.register_component(category, name, schema)
        return OrderedDict((k, v) for k, v in self._components.items() if v)

    def description_for(self, doc: Dict[str, Any], method: str) -> str:
        """Extract the description metadata and fallback on the whole docstring

        :param doc: a mapping from HTTP verb to the properties for serialization
        :param method: The HTTP Verb function for the route
        :return: The description as pulled from the docstring for the description property
        """
        parts = []
        if 'description' in doc:
            parts.append(doc['description'])
        if method in doc and 'description' in doc[method]:
            parts.append(doc[method]['description'])
        if doc[method]['docstring']['details']:
            parts.append(doc[method]['docstring']['details'])

        return '\n'.join(parts).strip()

    def parameters_for(self, doc: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """Get the list of param descriptions for output

        :param doc: a mapping from HTTP verb to the properties for serialization
        :return: a list of dict objects containing params as described by the openapi 3.0 spec
        """
        params = []
        for name, param in doc['params'].items():
            if 'ref' in param:
                if isinstance(param['ref'], str) and param['ref'].startswith('#/components/'):
                    params.append({'$ref': param['ref']})
                else:
                    params.append(self.serialize_schema(param['ref']))
                continue

            param['name'] = name
            if 'schema' not in param:
                param['schema'] = {}
            if 'type' not in param['schema'] and '$ref' not in param['schema']:
                param['schema']['type'] = 'string'
            if 'in' not in param:
                param['in'] = 'query'

            params.append(param)

        return params

    def operation_id_for(self, doc: Dict[str, Any], method: str) -> str:
        """Return the operation id to be used for openapi docs

        :param doc: a mapping from HTTP verb to the properties for serialization
        :param method: the HTTP Verb
        :return: The id str
        """
        return doc[method]['id'] if 'id' in doc[method] else self.api.default_id(doc['name'], method)

    def responses_for(self, doc: Dict[str, Any], method: str) -> Dict[HTTPStatus, Dict[str, Any]]:
        """Get the Response dictionary for a given route and HTTP verb

        :param doc: a mapping from HTTP verb to the properties for serialization
        :param method: the HTTP Verb to get the responses for
        :return: A dict mapping status codes to object descriptions as per the `openapi response object`__ spec.

        __  https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.1.md#responseObject
        """
        responses = {}
        for d in doc, doc[method]:
            if 'responses' in d:
                for code, response in d['responses'].items():
                    if isinstance(response, str):
                        description = response
                        validator = None
                        kwargs = {}
                    elif len(response) == 3:
                        description, validator, kwargs = response
                    elif len(response) == 2:
                        description, validator = response
                        kwargs = {}
                    else:
                        return ValueError('Unsupported response specification')
                    description = description or DEFAULT_RESPONSE_DESCRIPTION
                    if code in responses:
                        responses[code].update(description=description)
                    else:
                        responses[code] = {'description': description}
                    if validator:
                        if 'content' not in responses[code]:
                            responses[code]['content'] = {}
                        content_type = kwargs.get('content_type') or 'application/json'
                        if content_type not in responses[code]['content']:
                            responses[code]['content'][content_type] = {}
                        responses[code]['content'][content_type]['schema'] = self.serialize_schema(validator)
                    self.process_headers(responses[code], doc, method, kwargs.get('headers'))
        if not responses:
            responses[HTTPStatus.OK.value] = self.process_headers(DEFAULT_RESPONSE.copy(), doc, method)
        return responses

    def process_headers(self, response: Dict[str, Any], doc: Dict[str, Any], method: Optional[str]=None,
                        headers: Optional[Dict[str, Union[str, Dict[str, Any]]]]=None) -> Dict[str, Any]:
        """Properly form the header parameter objects according to the openapi 3.0 spec

        :param response: Response object definition
        :param doc: a mapping from HTTP verb to the properties for serialization
        :param method: the HTTP verb for specific requests or None for all in the resource
        :param headers: Header object dict to add to whatever is already in the resource and function decorators
        :return: The full set of headers for this particular route and request method joining the resource
                 level, method level and any additional headers passed in
        """
        method_doc = doc.get(method, {})
        if 'headers' in doc or 'headers' in method_doc or headers:
            response['headers'] = dict(
                (k, _clean_header(v)) for k, v in chain(
                    doc.get('headers', {}).items(),
                    method_doc.get('headers', {}).items(),
                    (headers or {}).items())
            )
        return response

    def serialize_schema(self, validator: ValidatorTypes) -> Dict[str, Any]:
        """Given a validator normalize the schema definition

        :param validator: either the name of a validator, a :class:`~jsonschema.Draft4Validator` instance,
                          or the actual type of the value. Passing a list or tuple will create a schema
                          for an array of that type
        :return: The schema as defined by the openapi 3.0 spec as a dict
        """
        if isinstance(validator, (list, tuple)):
            validator = validator[0]
            return {
                'type': 'array',
                'items': self.serialize_schema(validator)
            }
        elif isinstance(validator, Draft4Validator):
            return validator.schema
        elif isinstance(validator, str):
            validator = self.api.get_validator(validator)
            return validator.schema
        elif isinstance(validator, (type, type(None))) and validator in PY_TYPES:
            return {'type': PY_TYPES[validator]}

    def serialize_resource(self, resource: Union[Resource, Callable], path: str,
                           methods: Iterable[str]) -> Dict[str, Any]:
        """Use the docstring and any decorated info to create the resource object

        :param resource: the Resource object or view function
        :param path: the route path for this resource
        :param methods: The list of available HTTP verbs for this route
        :return: The dict conforming to the openapi 3.0 spec for a `path item object`__

        __ https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.1.md#pathItemObject
        """
        doc = self.extract_resource_doc(resource, path)
        if doc is False:
            return

        path = {}
        for method in [m.lower() for m in resource.methods or []]:
            methods = [m.lower() for m in methods or []]
            if doc[method] is False or methods and method not in methods:
                continue
            path[method] = self.serialize_operation(doc, method)
        return not_none(path)

    def serialize_operation(self, doc: Mapping[str, Any], method: str) -> Dict[str, Any]:
        """Serialize a single operation on the resource corresponding to a single HTTP verb

        :param doc: a mapping from HTTP verb to the properties for serialization
        :param method: The HTTP verb for this operation
        :return: The dict openapi representation to be converted to json for this operation
        """
        operation = {
            'summary': doc[method]['docstring']['summary'],
            'description': self.description_for(doc, method),
            'tags': [],
            'parameters': self.parameters_for(doc[method]) or None,
            'responses': self.responses_for(doc, method) or None,
            'operationId': self.operation_id_for(doc, method)
        }
        body = merge(self.expected_params(doc), self.expected_params(doc[method]))
        if body:
            operation['requestBody'] = body
        if doc.get('deprecated') or doc[method].get('deprecated'):
            operation['deprecated'] = True
        return not_none(operation)

    def extract_resource_doc(self, resource: Union[Resource, Callable], path: str) -> Dict[str, Any]:
        """Return the doc mapping for this resource that we saved on it

        :param resource: The :class:`Resource` derived class or decorated view function
        :param path: The route for this resource
        :return: a mapping from HTTP verb to the properties for serialization

        This returns the object that is passed into the `serialize_*` functions that expect
        a `doc` parameter
        """
        doc = getattr(resource, '__apidoc__', {})
        if doc is False:
            return False
        doc['name'] = resource.__name__
        params = merge(doc.get('params', OrderedDict()), _extract_path_params(path))
        doc['params'] = params
        for method in [m.lower() for m in resource.methods or []]:
            method_doc = doc.get(method, OrderedDict())
            method_impl = getattr(resource, method)
            if hasattr(method_impl, 'im_func'):
                method_impl = method_impl.im_func
            elif hasattr(method_impl, '__func__'):
                method_impl = method_impl.__func__
            method_doc = merge(method_doc, getattr(method_impl, '__apidoc__', OrderedDict()))
            if method_doc is not False:
                method_doc['docstring'] = parse_docstring(method_impl)
                method_params = method_doc.get('params', {})
                inherited_params = OrderedDict((k,v) for k, v in params.items())
                method_doc['params'] = merge(inherited_params, method_params)
            doc[method] = method_doc
        return doc

    def expected_params(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Return the `Media Type object
        <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.1.md#mediaTypeObject>`_
        for the expected request body.

        :param doc: a mapping from HTTP verb to the properties for serialization
        :return: a dict containing the content type and schemas for the requestBody
        """
        params = OrderedDict()
        if 'expect' not in doc:
            return params

        for expect in doc.get('expect', []):
            validator, content_type, kwargs = get_expect_args(expect)
            if isinstance(validator, str):
                validator = self.api.get_validator(validator)
            elif not isinstance(validator, Draft4Validator):
                continue

            schema = self.serialize_schema(validator)
            if '$ref' in schema and '/components/requestBodies/' in schema['$ref']:
                return schema

            params[content_type] = not_none(dict({
                'schema': self.serialize_schema(validator)
            }, **kwargs))

        return {'content': params}
