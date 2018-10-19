from quart import Quart, jsonify, Blueprint
from quart.views import http_method_funcs
import json
from jsonschema import Draft4Validator, RefResolver, FormatChecker
from jsonschema.exceptions import ValidationError
import logging
from inspect import isclass
from http import HTTPStatus
from .cors import crossdomain
from .resource import Resource
from .utils import cached_property, merge, camel_to_snake
from .typing import ValidatorTypes, ExpectedDescList
from typing import Optional, Union, Dict, Callable, Iterable, Tuple, Any

logger = logging.getLogger('quart.serving')

def _expand_params_desc(data: Dict[str, Any]) -> None:
    """Used to convert `{'param': 'Description String'}` into
    `{'param': { 'description': 'Description String'}}`

    :param data: A dictionary containing a 'params' property
    """
    if 'params' in data:
        for name, description in data['params'].items():
            if isinstance(description, str):
                data['params'][name] = {'description': description}

class BaseRest(object):
    """Base object for handling the RESTful resources for routing and generating swagger. Used by :class:`Pint`
    and :class:`PintBlueprint`
    """

    def __init__(self, *args: Any, title: Optional[str]=None, contact: Optional[str]=None,
                 contact_url: Optional[str]=None, contact_email: Optional[str]=None,
                 version: str='1.0', description: Optional[str]=None, validate: bool=True,
                 base_model_schema: Optional[Union[str, Dict[str, Any], RefResolver]]=None,
                 **kwargs: Any) -> None:
        r"""Construct the Base Rest object

        :param \*args: non-keyword args for :class:`~quart.Quart`
        :param title: The title for the info section
        :param contact: Contact name for docs
        :param contact_url: URL for Contact property of the info section
        :param contact_email: Email Contact for docs
        :param version: Version to put in the docs
        :param description: Textual description for the openapi json
        :param validate: The default validation state for routes that have an expect
        :param base_model_schema: Allows defining a base jsonschema to reference models either by
                                  file name, or by passing in the actual schema dict.
        :param \*\*kwargs: keyword args other than the above will be passed to the :class:`~quart.Quart`
                         constructor.
        """
        super().__init__(*args, **kwargs)
        self._ref_resolver = None
        self._validators = {}
        self._validate = validate
        self._resources = []
        self._schema = None
        self.title = title
        self.description = description
        self.version = version
        self.contact = contact
        self.contact_url = contact_url
        self.contact_email = contact_email
        if base_model_schema is not None:
            if isinstance(base_model_schema, str):
                with open(base_model_schema, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                self._ref_resolver = RefResolver.from_schema(schema)
            elif isinstance(base_model_schema, dict):
                self._ref_resolver = RefResolver.from_schema(base_model_schema)
            elif isinstance(base_model_schema, RefResolver):
                self._ref_resolver = base_model_schema
        self.register_error_handler(ValidationError, self.handle_json_validation_exc)

    @staticmethod
    def handle_json_validation_exc(error: ValidationError) -> Dict[str, Union[str, Dict[str, str]]]:
        """Function to handle validation errors

        The constructor will register this function to handle a :exc:`~jsonschema.exceptions.ValidationError`
        which is thrown by the :mod:`jsonschema` validation routines.

        :param error: The exception that was raised
        :return: Json message with the validation error

        .. seealso::

           :meth:`quart.Quart.register_error_handler`
               Registering error handlers with quart
        """
        logger.error('request body validation failed, returning error: msg: %s, instance: %r',
                     error.message, error.instance)
        return jsonify({
            'message': 'Request Body failed validation',
            'error': {
                'msg': error.message,
                'value': error.instance,
                'schema': error.schema
            }
        }), HTTPStatus.BAD_REQUEST.value


    @property
    def resources(self) -> Iterable[Tuple[Resource, str, Iterable[str]]]:
        """The list of resource tuples that have been added so far.

        The tuple contains the object itself, the path and the list of methods it supports
        """
        return self._resources

    @property
    def base_model(self) -> Optional[RefResolver]:
        """The :class:`~jsonschema.RefResolver` created by processing the file or schema that was passed to
        :meth:`__init__`
        """
        return self._ref_resolver

    @cached_property
    def __schema__(self) -> Dict[str, Union[str, Dict[str, Any]]]:
        """The schema produced by the Swagger object using the information in this instance"""
        if not self._schema:
            from .swagger import Swagger
            self._schema = Swagger(self).as_dict()
        return self._schema

    def get_validator(self, name: str) -> Optional[Draft4Validator]:
        """Get a specific :class:`~jsonschema.Draft4Validator` instance by name

        :param name: The validator name to lookup
        :return: the :class:`~jsonschema.Draft4Validator` object or None
        """
        return self._validators[name] if name in self._validators else None

    def _add_resource(self, resource: Union[Resource, Callable],
                     path: str, methods: Iterable[str], endpoint: Optional[str]=None, *args,
                      provide_automatic_options: bool=True, **kwargs: Any) -> None:
        r"""Called by :meth:`route` in order to process the resource or view function and only add it to the
        list of openapi resources if it's a class, allowing paths to be left out of the openapi documentation
        by declaring them as functions.

        :param resource: The class or view function to add
        :param path: the route path
        :param methods: list of available methods (GET, POST, etc.)
        :param endpoint: Endpoint alias, defaults to the function or class name
        :param \*args: any additional args needed to be passed to the view instance
        :param provide_automatic_options: Override automatic OPTIONS if set, to either True or False
        """
        view_func = resource
        if isclass(resource):
            view_func = resource.as_view(camel_to_snake(resource.__name__), *args)
            methods = list(resource.methods)
            self._resources.append((resource, path, methods))
        super().add_url_rule(path, endpoint, view_func, methods,
                          provide_automatic_options=provide_automatic_options, **kwargs)

    def param(self, name: str, description: Optional[str]=None,
              _in: str='query', **kwargs: Dict[str, Any]) -> Callable:
        r"""Decorator for describing parameters for a given resource or specific request method.

        :param name: Parameter name in documention
        :param description: the description property of the parameter object
        :param _in: Location of the parameter: query, header, path, cookie
        :param \*\*kwargs: mapping of properties to forward for the openapi docs

        If put at the class level, it'll add the parameter to all method types. For path params
        you should use :meth:`doc` instead which will automatically handle path params instead of
        having to manually set `_in` to 'path'

        See the following example:

        .. code-block:: python

              @app.route('/header')
              @app.param('Expected-Header', description='Header Parameter for all method types', _in='header')
              class Simple(Resource):

                @app.param('id', description='query param id just for get method', schema={'type': 'integer'})
                async def get(self):
                  hdr_value = request.headers['Expected-Header']
                  id = request.args['id']
                  return f"{id} with {hdr_value}"

                @app.param('foobar', description='foobar will show up for the post method, but not get',
                           _in='cookie', style='form')
                async def post(self):
                  # the openapi documentation will contain both the Expected-Header and
                  # the 'foobar' cookie params in it
                  ...
                  return "Success"
        """
        param = kwargs
        param['in'] = _in
        param['description'] = description
        return self.doc(params={name: param})

    def response(self, code: HTTPStatus, description: str, validator: ValidatorTypes=None,
                 **kwargs: Dict[str, Any]) -> Callable:
        r"""Decorator for documenting the response from a route

        :param code: The HTTP Response code for this response
        :param description: The description property for this response
        :param validator: pass a string to refer to a specific validator by name, a
                          :class:`~jsonschema.Draft4Validator` instance such as from :meth:`get_validator`,
                          :meth:`create_ref_validator` or :meth:`create_validator`, a jsonschema dict,
                          or the actual expected type of the response if a primitive
        :param \*\*kwargs: All other keyword args will be forwarded as properties of the response object

        Use this decorator for adding the documentation to describe a possible response from
        the route, can be called multiple times with different status codes to describe different
        responses.

        .. code-block:: python

              @app.route('/sample')
              class Sample(Resource):

                @app.response(HTTPStatus.OK, description="OK")
                @app.response(HTTPStatus.BAD_REQUEST, "json response failure", int, headers={'Foobar': 'foo'})
                async def get(self):
                  ...
        """
        return self.doc(responses={code: (description, validator, kwargs)})

    def route(self, path: str, methods: Iterable[str]=['GET'], *args, **kwargs) -> Callable:
        r"""Decorator for establishing routes

        :param path: the path to route on, should start with a `/`, may contain params converters
        :param methods: list of HTTP verbs allowed to be routed
        :param \*args: will forward extra arguments to the :meth:`base class route function <quart.Quart.route>`

        Ensures we add the route's documentation to the openapi docs and merge the properties correctly,
        should work identically to using the base method.

        .. seealso:: Base class version :meth:`~quart.Quart.route`
        """
        def decorator(func_or_viewcls: Union[Resource, Callable]) -> Union[Resource, Callable]:
            doc = kwargs.pop('doc', None)
            if doc is not None:
                self._handle_doc(func_or_viewcls, doc)
            self._add_resource(func_or_viewcls, path, methods, *args, **kwargs)
            return func_or_viewcls
        return decorator

    def create_ref_validator(self, name: str, category: str) -> Draft4Validator:
        """Use the :attr:`base_model` to resolve the component category and name and create a
        :class:`~jsonschema.Draft4Validator`

        :param name: The name of the model
        :param category: The category under 'components' to look in
        :return: The validator object

        The resulting validator can be passed into decorators like :meth:`param` or :meth:`response`
        and will be used to create the schema in the openapi json output or passed into :meth:`expect`
        to use it for actually validating a request against the schema. It will be output as a '$ref'
        object in the resulting openapi json output.

        .. seealso:: The :meth:`expect` decorator

        .. todo:: Ensure that models with the same name in different categories don't conflict
        """
        validator = Draft4Validator({ '$ref': f'#/components/{category}/{name}' }, resolver=self._ref_resolver, format_checker=FormatChecker())
        self._validators[name] = validator
        return validator

    def create_validator(self, name: str, schema: Dict[str, Any]) -> Draft4Validator:
        """Create a validator from a schema

        :param name: The name of this validator
        :param schema: A dict which is a valid Openapi 3.0 schema
        :return: the validator object

        You can use references to models that are in the :attr:`base_model` as that will be used to resolve
        any references such as `#/components/requestBodies/sample`.

        .. todo:: Ensure that models with the same name in different categories don't conflict with each other

        .. seealso:: The :meth:`expect` decorator
        """
        validator = Draft4Validator(schema, resolver=self._ref_resolver, format_checker=FormatChecker())
        self._validators[name] = validator
        return validator

    def _handle_doc(self, cls: Callable, doc: Dict[str, Any]) -> None:
        """Internal function for merging doc specs for various HTTP verbs and handling expects"""
        # adapted from flask_restplus
        _expand_params_desc(doc)
        for http_method in http_method_funcs:
            if http_method in doc:
                if doc[http_method] is False:
                    continue
                _expand_params_desc(doc[http_method])
                if 'expect' in doc[http_method] and not isinstance(doc[http_method]['expect'], (list, tuple)):
                    doc[http_method]['expect'] = [doc[http_method]['expect']]
        cls.__apidoc__ = merge(getattr(cls, '__apidoc__', {}), doc)

    def doc(self, **kwargs: Dict[str, Any]) -> Callable:
        """Generic decorator for adding docs via keys pointing to dictionaries

        Examples:

        .. code-block:: python

              @app.route('/<string:table>')
              @app.doc(params={'table': 'Table Description'})
              class Table(Resource):
                async def get(self, table):
                  ...

        .. code-block:: python

              @app.route('/<int:table>')
              class Table(Resource):
                @app.doc(params={'table': 'Table Desc'}, responses={HTTPStatus.OK: ('desc')})
                async def get(self, table):
                  ...
        """
        def wrapper(documented: Callable) -> Callable:
            self._handle_doc(documented, kwargs)
            return documented
        return wrapper

    def expect(self, *inputs: ExpectedDescList, **kwargs: Dict[str, Any]) -> Callable:
        r"""Define the expected request schema

        :param \*inputs: one or more inputs that are either a validator or a tuple of the form
                         Tuple[validator, content_type, Dict of properties]. properly handles either
                         1, 2, or all 3 members existing.
        :param \*\*kwargs: currently only recognizes 'validate' as a keyword arg which can override the
                           bool that was passed into :meth:`__init__` to turn validation on or off for this
                           particular request body

        Code Example:

        .. code-block:: python

              request = app.create_validator('sample', {
                'type': 'object',
                'properties': {
                  'columns': {
                    'type': 'array',
                    'items': { 'type': 'string' }
                  },
                  'rows': {
                    'type': 'array',
                    'items': {
                      'oneOf': [
                        {'type': 'integer'},
                        {'type': 'number'},
                        {'type': 'string'}
                      ]
                    }
                  }
                }
              })
              @app.route('/sample')
              class Sample(Resource):
                @app.expect(request)
                async def post(self):
                  # if the request body isn't json and doesn't match the above schema
                  # we'll never even get here, it'll be rejected with a bad request status
                  ...

        Another Example:

        .. code-block:: python

              stream = app.create_validator('binary_stream', {'type': 'string', 'format': 'binary'})
              string_data = app.create_validator('string', {'type': 'string'})
              @app.route('/sample')
              class Sample(Resource):
                @app.expect((stream, 'application/octet-stream', {'example': '0xACDEFD'}),
                            ('string', 'text/plain', {'examples': {
                                                        'ex1': {
                                                          'summary': 'example1',
                                                          'value': 'foobar'
                                                        }
                                                     }}))
                async def post(self):
                  # if the request doesn't have a Content-Type header set to 'application/octet-stream'
                  # or 'text/plain' it will be rejected as a bad request.
                  ...

        In the above example, the examples will be in the openapi docs as per the `openapi 3.0 spec
        <https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.1.md#request-body-object>`_.

        .. todo:: figure out a good way to set the description for the requestBody itself, probably through
                  the `kwargs`
        """
        expect = []
        params = {
            'validate': kwargs.get('validate', None) or self._validate,
            'expect': expect
        }
        for param in inputs:
            expect.append(param)
        return self.doc(**params)

    @staticmethod
    def default_id(resource: str, method: str) -> str:
        """function for creating a default operation id from a resource and method

        :param resource: name of the resource endpoint
        :param method: the HTTP verb
        :return: the id converting camel case to snake_case
        """
        return '{0}_{1}'.format(method, camel_to_snake(resource))

class Pint(BaseRest, Quart):
    """Use this instead of instantiating :class:`quart.Quart`

    This takes the place of instantiating a :class:`quart.Quart` instance. It will forward
    any init arguments to Quart and takes arguments to fill out the metadata for the openapi
    documentation it generates that will automatically be accessible via the '/openapi.json'
    route.
    """

    def __init__(self, *args, **kwargs) -> None:
        """ Construct the Pint object, see :meth:`BaseRest.__init__` for an explanation of the args and kwargs."""
        super().__init__(*args, **kwargs)
        self.config['JSON_SORT_KEYS'] = False
        self.add_url_rule('/openapi.json', 'openapi', SwaggerView.as_view('swaggerview', self), ['GET', 'OPTIONS'])

class PintBlueprint(BaseRest, Blueprint):
    """Use this instead of :class:`quart.Blueprint` objects to allow using Resource class objects with them"""

    def __init__(self, *args, **kwargs) -> None:
        """Will forward all arguments and keyword arguments to Blueprints"""
        super().__init__(*args, **kwargs)

    def register(self, app: Pint, first_registration: bool, *, url_prefix: Optional[str]=None) -> None:
        """override the base :meth:`~quart.Blueprint.register` method to add the resources to the app registering
        this blueprint, then call the parent register method
        """
        prefix = url_prefix or self.url_prefix
        app._resources.extend([(res, f'{prefix}{path}', methods) for res, path, methods in self._resources])
        super().register(app, first_registration, url_prefix=url_prefix)

class SwaggerView(Resource):
    """The :class:`Resource` used for the '/openapi.json' route

    It also uses CORS to set the Access-Control-Allow-Origin header to "*" for this route so that the
    openapi.json can be accessible from other domains.

    .. todo:: Allow customizing the origin for CORS on the openapi.json
    """
    def __init__(self, api: Pint) -> None:
        """Construct the SwaggerView

        :param api: will be an instance of a :class:`Pint` object, the :attr:`~Pint.__schema__`
                    property will be returned for `get` requests to '/openapi.json'
        """
        self.api = api

    # use CORS to allow other origins to access the openapi.json route
    # this way it can also be used with swagger UI
    @crossdomain(origin='*')
    async def get(self):
        return jsonify(self.api.__schema__), 200
