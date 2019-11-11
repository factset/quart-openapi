"""cors.py

Provide decorator for CORS requests to provide the openapi.json file
"""

from datetime import timedelta
from functools import update_wrapper
from typing import Callable, Iterable, Union

from quart import current_app, make_response, request

# pylint: disable=too-many-arguments
def crossdomain(origin: str = None, methods: Iterable[str] = None, headers: Union[str, Iterable[str]] = None,
                expose_headers: Union[str, Iterable[str]] = None, max_age: Union[int, timedelta] = 21600,
                attach_to_all: bool = True, automatic_options: bool = True, credentials: bool = False) -> Callable:
    """Decorator for `CORS <https://fetch.spec.whatwg.org/#http-cors-protocol>`_ adapted from
    http://flask.pocoo.org/snippets/56/

    :param origin: value for `Access-Control-Allow-Origin` header
    :param methods: str or list[str] of HTTP verbs for the `Access-Control-Allow-Methods`, defaults
                    to 'OPTIONS, HEAD' + any available verb functions on the class
    :param headers: str or list[str] for the `Access-Control-Allow-Headers` header
    :param expose_headers: str or list[str] for the `Access-Control-Expose-Headers` header
    :param max_age: the number of seconds for the `Access-Control-Max-Age` header.
    :param attach_to_all: if `False`, the CORS headers will only be attached to `OPTIONS` requests
    :param automatic_options: if `False`, will look for an options function in the resource, otherwise
                              the default options response will be used for OPTIONS requests,
                              and the CORS headers will be attached
    :param credentials: the value of the `Access-Control-Allow-Credentials` header

    This decorator should be used on individual route functions like so:

    .. code-block:: python

          @app.route('/foobar', methods=['GET','OPTIONS'])
          class CORS(Resource):
            @crossdomain(origin='*')
            async def get(self):
              ...

    This would allow Cross Origin requests to make get requests to '/foobar'.
    """
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if expose_headers is not None and not isinstance(expose_headers, str):
        expose_headers = ', '.join(x.upper() for x in expose_headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    async def get_methods():
        if methods is not None:
            return methods

        options_resp = await current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(func):
        async def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = await current_app.make_default_options_response()
            else:
                resp = await make_response(await func(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            hdrs = resp.headers

            hdrs['Access-Control-Allow-Origin'] = origin
            hdrs['Access-Control-Allow-Methods'] = await get_methods()
            hdrs['Access-Control-Max-Age'] = str(max_age)
            if credentials:
                hdrs['Access-Control-Allow-Credentials'] = 'true'
            if headers is not None:
                hdrs['Access-Control-Allow-Headers'] = headers
            if expose_headers is not None:
                hdrs['Access-Control-Expose-Headers'] = expose_headers
            return resp

        func.provide_automatic_options = False
        return update_wrapper(wrapped_function, func)
    return decorator
