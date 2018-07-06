from typing import Dict, Any, Tuple, Callable
from quart import request
from quart.views import MethodView
from quart.typing import ResponseReturnValue
import logging
from .typing import ValidatorTypes, ExpectedDescList

logger = logging.getLogger('quart.serving')

def get_expect_args(expect: ExpectedDescList,
                     default_content_type: str='application/json'
) -> Tuple[ValidatorTypes, str, Dict[str, Any]]:
    """Normalize the different tuple sizes for the expect decorator

    :param expect: Either a validator, a tuple of size 1 containing a validator,
                   a tuple of the validator and content type or a tuple of the
                   validator, content_type and a dict of other properties to add
    :return: Regardless of how the expect decorator was used, returns a tuple containing
             the validator, the content type and any extra kwargs
    """
    content_type = default_content_type
    kwargs = {}
    if isinstance(expect, tuple):
        if len(expect) == 2:
            expect, content_type = expect
        elif len(expect) == 3:
            expect, content_type, kwargs = expect
        else:
            expect = expect[0]
    return (expect, content_type, kwargs)

class Resource(MethodView):
    """Inherit from this to create RESTful routes with openapi docs

    A Resource subclass needs only to implement async functions corresponding to the HTTP
    verbs you want to handle. Utilizing the decorators from :class:`Pint` you can set
    the route, params, responses, and so on that will show up in the openapi documentation.

    An example is,

    .. code-block:: python

          app = Pint('sample')
          @app.route('/<id>')
          class SimpleRoute(Resource):
            async def get(self, id):
              return f"ID is {id}"

    That will enable a route '/<id>' which will return the string "ID is <id>" when called
    by a GET request. If using :meth:`Pint.expect` to define the expected request body,
    it will perform validation unless validate is set to false.
    """

    async def dispatch_request(self, *args: Any, **kwargs: Any) -> ResponseReturnValue:
        """Can be overridden instead of creating verb functions

        This will be called with the request view_args, i.e. any url parameters
        """
        handler = getattr(self, request.method.lower(), None)
        if handler is None and request.method == 'HEAD' or request.method == 'OPTIONS':
            handler = getattr(self, 'get', None)

        await self.validate_payload(handler)
        return await handler(*args, **kwargs)

    async def validate_payload(self, func: Callable) -> bool:
        """This will perform validation

        Will check the api docs of the class as set by using the decorators in :class:`Pint`
        and if an expect was present without `validate` set to `False` or `None`, it will
        attempt to validate any request against the schema if json, or ensure the content_type
        matches at least.
        """
        if getattr(func, '__apidoc__', False) is not False:
            doc = func.__apidoc__
            validate = doc.get('validate', None)
            if validate:
                for expect in doc.get('expect', []):
                    validator, content_type, _ = get_expect_args(expect)
                    if content_type == 'application/json' and request.is_json:
                        data = await request.get_json(force=True, cache=True)
                        return validator.validate(data)
                    elif content_type == request.mimetype:
                        return
                logger.error("Request didn't pass any of the available validations")
                raise ValueError("request didn't pass validation")

