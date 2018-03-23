from quart import Quart, request, jsonify
from quart.views import MethodView, HTTP_METHOD_FUNCTIONS
from quart.routing import ROUTE_VAR_RE, Map as RouteMap
import json
from jsonschema import Draft4Validator, RefResolver, FormatChecker
from jsonschema.exceptions import ValidationError
import logging
from copy import copy
from itertools import chain
from inspect import isclass
from collections import OrderedDict, Hashable
from http import HTTPStatus
from .cors import crossdomain
from .utils import parse_docstring, cached_property, extract_path, not_none, merge, camel_to_snake

logger = logging.getLogger('quart.serving')

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

def expand_params_desc(data):
    if 'params' in data:
        for name, description in data['params'].items():
            if isinstance(description, str):
                data['params'][name] = {'description': description}

def _parse_rule(rule):
    variable_names = set()
    for match in ROUTE_VAR_RE.finditer(rule):
        named_groups = match.groupdict()
        yield (named_groups['converter'], named_groups['variable'])

def extract_path_params(path):
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

def _clean_header(header):
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

def _get_expect_args(expect, default_content_type='application/json'):
    content_type = default_content_type
    examples = None
    if isinstance(expect, tuple):
        if len(expect) == 2:
            expect, content_type = expect
        elif len(expect) == 3:
            expect, content_type, examples = expect
        else:
            expect = expect[0]
    return (expect, content_type, examples)

class SwagGen(Quart):
    def __init__(self, *args, title=None, contact=None, contact_url=None, contact_email=None,
                 version='1.0', description=None, base_model_schema=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._ref_resolver = None
        self._validators = {}
        self._validate = True
        self._resources = []
        self._schema = None
        self.title = title
        self.description = description
        self.version = version
        self.contact = contact
        self.contact_url = contact_url
        self.contact_email = contact_email
        self.config['JSON_SORT_KEYS'] = False
        if base_model_schema is not None:
            schema = None
            with open(base_model_schema, 'r') as f:
                schema = json.load(f)
            self._ref_resolver = RefResolver.from_schema(schema)
        self.add_url_rule('/swagger.json', SwaggerView.as_view('swaggerview', self), ['GET', 'OPTIONS'])
        self.register_error_handler(ValidationError, self.handle_json_validation_exc)

    @staticmethod
    def handle_json_validation_exc(error):
        logger.error('request body validation failed, returning error')
        return jsonify({
            'message': 'Request Body failed validation',
            'error': {
                'msg': error.message,
                'value': error.instance,
                'schema': error.schema
            }
        }), HTTPStatus.BAD_REQUEST.value

    @property
    def base_model(self):
        return self._ref_resolver

    @property
    def resources(self):
        return self._resources

    @cached_property
    def __schema__(self):
        if not self._schema:
            self._schema = Swagger(self).as_dict()
        return self._schema

    def get_validator(self, name):
        return self._validators[name] if name in self._validators else None

    def add_resource(self, resource, path, methods, *args, provide_automatic_options=True):
        view_func = resource
        if isclass(resource):
            view_func = resource.as_view(camel_to_snake(resource.__name__), *args)
            methods = list(resource.methods)
            self._resources.append((resource, path, methods))
        self.add_url_rule(path, view_func, methods, provide_automatic_options=provide_automatic_options)

    def param(self, name, description=None, _in='query', **kwargs):
        param = kwargs
        param['in'] = _in
        param['description'] = description
        return self.doc(params={name: param})

    def response(self, code, description, validator=None, **kwargs):
        return self.doc(responses={code: (description, validator, kwargs)})

    def route(self, path, methods=['GET'], *args, **kwargs):
        def decorator(func_or_viewcls):
            doc = kwargs.pop('doc', None)
            if doc is not None:
                self._handle_doc(func_or_viewcls, doc)
            self.add_resource(func_or_viewcls, path, methods, *args, **kwargs)
            return func_or_viewcls
        return decorator

    def create_ref_validator(self, name, category):
        validator = Draft4Validator({ '$ref': f'#/components/{category}/{name}' }, resolver=self._ref_resolver, format_checker=FormatChecker())
        self._validators[name] = validator
        return validator

    def create_validator(self, name, schema):
        validator = Draft4Validator(schema, resolver=self._ref_resolver, format_checker=FormatChecker())
        self._validators[name] = validator
        return validator

    def _handle_doc(self, cls, doc):
        # adapted from flask_restplus
        expand_params_desc(doc)
        for http_method in HTTP_METHOD_FUNCTIONS:
            if http_method in doc:
                if doc[http_method] is False:
                    continue
                expand_params_desc(data)
                if 'expect' in doc[http_method] and not isinstance(doc[http_method]['expect'], (list, tuple)):
                    doc[http_method]['expect'] = [doc[http_method]['expect']]
        cls.__apidoc__ = merge(getattr(cls, '__apidoc__', {}), doc)

    def doc(self, **kwargs):
        def wrapper(documented):
            self._handle_doc(documented, kwargs)
            return documented
        return wrapper

    def expect(self, *inputs, **kwargs):
        expect = []
        params = {
            'validate': kwargs.get('validate', None) or self._validate,
            'expect': expect
        }
        for param in inputs:
            expect.append(param)
        return self.doc(**params)

    @staticmethod
    def default_id(resource, method):
        return '{0}_{1}'.format(method, camel_to_snake(resource))

class Swagger(object):
    def __init__(self, api):
        self.api = api
        self._components = OrderedDict([('schemas', OrderedDict()),
                                        ('responses', OrderedDict()),
                                        ('parameters', OrderedDict()),
                                        ('examples', OrderedDict()),
                                        ('requestBodies', OrderedDict()),
                                        ('headers', OrderedDict()),
                                        ('securitySchemes', OrderedDict())])

    def as_dict(self):
        infos = {
            'title': self.api.title or 'Swagger App',
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
                { 'url': ''.join([self.api.config['PREFERRED_URL_SCHEME'], '://', self.api.config['SERVER_NAME'] or '']) }
            ],
            'paths': paths,
            'components': components
        }
        return not_none(spec)

    def register_component(self, category, name, schema):
        if category not in self._components:
            raise ValueError('invalid category for components')
        self._components[category][name] = schema

    def serialize_components(self):
        base_components = self.api.base_model.resolve('#/components')[1]
        for category, val in base_components.items():
            for name, schema in val.items():
                self.register_component(category, name, schema)
        return OrderedDict((k, v) for k, v in self._components.items() if v)

    def description_for(self, doc, method):
        '''Extract the description metadata and fallback on the whole docstring'''
        parts = []
        if 'description' in doc:
            parts.append(doc['description'])
        if method in doc and 'description' in doc[method]:
            parts.append(doc[method]['description'])
        if doc[method]['docstring']['details']:
            parts.append(doc[method]['docstring']['details'])

        return '\n'.join(parts).strip()

    def parameters_for(self, doc):
        params = []
        for name, param in doc['params'].items():
            param['name'] = name
            if 'schema' not in param:
                param['schema'] = {}
            if 'type' not in param['schema']:
                param['schema']['type'] = 'string'
            if 'in' not in param:
                param['in'] = 'query'

            params.append(param)

        return params

    def operation_id_for(self, doc, method):
        return doc[method]['id'] if 'id' in doc[method] else self.api.default_id(doc['name'], method)

    def responses_for(self, doc, method):
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

    def process_headers(self, response, doc, method=None, headers=None):
        method_doc = doc.get(method, {})
        if 'headers' in doc or 'headers' in method_doc or headers:
            response['headers'] = dict(
                (k, _clean_header(v)) for k, v in chain(
                    doc.get('headers', {}).items(),
                    method_doc.get('headers', {}).items(),
                    (headers or {}).items())
            )
        return response

    def serialize_schema(self, validator):
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

    def serialize_resource(self, resource, path, methods):
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

    def serialize_operation(self, doc, method):
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

    def extract_resource_doc(self, resource, path):
        doc = getattr(resource, '__apidoc__', {})
        if doc is False:
            return False
        doc['name'] = resource.__name__
        params = merge(doc.get('params', OrderedDict()), extract_path_params(path))
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

    def expected_params(self, doc):
        params = OrderedDict()
        if 'expect' not in doc:
            return params

        for expect in doc.get('expect', []):
            validator, content_type, examples = _get_expect_args(expect)
            if isinstance(expect, str):
                validator = self.api.get_validator(expect)
            elif isinstance(expect, Draft4Validator):
                validator = expect
            else:
                validator = None

            if validator is None:
                continue

            schema = self.serialize_schema(validator)
            if '$ref' in schema and '/components/requestBodies/' in schema['$ref']:
                return schema

            params[content_type] = not_none({
                'schema': self.serialize_schema(validator),
                'examples': examples if examples else None,
            })

        return {'content': params}

class Resource(MethodView):
    async def dispatch_request(self, *args, **kwargs):
        handler = getattr(self, request.method.lower(), None)
        if handler is None and request.method == 'HEAD' or request.method == 'OPTIONS':
            handler = getattr(self, 'get', None)

        await self.validate_payload(handler)
        return await handler(*args, **kwargs)

    async def validate_payload(self, func):
        rval = True
        if getattr(func, '__apidoc__', False) is not False:
            doc = func.__apidoc__
            validate = doc.get('validate', None)
            if validate:
                for expect in doc.get('expect', []):
                    validator, content_type, _ = _get_expect_args(expect)
                    if content_type == 'application/json' and request.is_json:
                        data = await request.get_json(force=True, cache=True)
                        return validator.validate(data)
                    elif content_type == request.mimetype:
                        return
                raise ValueError("request didn't pass validation")

class SwaggerView(Resource):
    def __init__(self, api):
        self.api = api

    @crossdomain(origin='*')
    async def get(self):
        return jsonify(self.api.__schema__), 200

