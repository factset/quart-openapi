# pylint: disable=missing-module-docstring,missing-class-docstring
from http import HTTPStatus

from quart import Blueprint, ResponseReturnValue, abort, request, url_for
from quart.views import MethodView
import pytest
from quart_openapi import Pint, PintBlueprint, Resource

# pylint: disable=unused-variable,misplaced-comparison-constant,missing-function-docstring,import-outside-toplevel

@pytest.mark.asyncio
async def test_root_endpoint_blueprint(app: Pint, req_ctx) -> None:
    blueprint = Blueprint('blueprint', __name__)

    @blueprint.route('/page/')
    async def route() -> ResponseReturnValue:
        return 'OK'

    app.register_blueprint(blueprint)
    async with req_ctx(app, '/page/', method='GET'):
        assert request.blueprint == 'blueprint'
        assert '/page/' == url_for('blueprint.route')

@pytest.mark.asyncio
async def test_blueprint_url_prefix(app: Pint, req_ctx) -> None:
    blueprint = Blueprint('blueprint', __name__)
    prefix = Blueprint('prefix', __name__, url_prefix='/prefix')

    @app.route('/page/')
    @blueprint.route('/page/')
    @prefix.route('/page/')
    async def route() -> ResponseReturnValue:
        return 'OK'

    app.register_blueprint(blueprint, url_prefix='/blueprint')
    app.register_blueprint(prefix)

    async with req_ctx(app, '/', method='GET'):
        assert '/page/' == url_for('route')
        assert '/prefix/page/' == url_for('prefix.route')
        assert '/blueprint/page/' == url_for('blueprint.route')

    async with req_ctx(app, '/page/', method='GET'):
        assert request.blueprint is None

    async with req_ctx(app, '/prefix/page/', method='GET'):
        assert request.blueprint == 'prefix'

    async with req_ctx(app, '/blueprint/page/', method='GET'):
        assert request.blueprint == 'blueprint'


@pytest.mark.asyncio
async def test_blueprint_error_handler(app: Pint) -> None:
    blueprint = Blueprint('blueprint', __name__)

    @blueprint.route('/error/')
    async def error() -> None:
        abort(409)
        return 'OK'

    @blueprint.errorhandler(409)
    async def handler(_: Exception) -> ResponseReturnValue:
        return 'Something Unique', 409

    app.register_blueprint(blueprint)

    response = await app.test_client().get('/error/')
    assert response.status_code == 409
    assert b'Something Unique' in await response.get_data()

@pytest.mark.asyncio
async def test_blueprint_method_view(app: Pint) -> None:
    blueprint = Blueprint('blueprint', __name__)

    class Views(MethodView):
        async def get(self) -> ResponseReturnValue:
            return 'GET'

        async def post(self) -> ResponseReturnValue:
            return 'POST'

    blueprint.add_url_rule('/', view_func=Views.as_view('simple'))
    app.register_blueprint(blueprint)

    test_client = app.test_client()
    response = await test_client.get('/')
    assert 'GET' == (await response.get_data(as_text=True))
    response = await test_client.post('/')
    assert 'POST' == (await response.get_data(as_text=True))

@pytest.mark.asyncio
async def test_pint_blueprint_openapi(app: Pint, req_ctx) -> None:
    blueprint = PintBlueprint('blueprint', __name__, url_prefix='/blueprint')
    app.register_blueprint(blueprint)

    async with req_ctx(app, '/', method='GET'):
        assert '/openapi.json' == url_for('openapi')


@pytest.mark.asyncio
async def test_blueprint_resource(app: Pint) -> None:
    blueprint = PintBlueprint('blueprint', __name__)

    @blueprint.route('/testing')
    class Testing(Resource):
        async def get(self):
            return 'GET'

        async def post(self):
            return 'POST'

    app.register_blueprint(blueprint)

    client = app.test_client()
    response = await client.post('/testing')
    assert 'POST' == (await response.get_data(as_text=True))
    response = await client.get('/testing')
    assert 'GET' == (await response.get_data(as_text=True))

@pytest.mark.asyncio
async def test_openapi_with_blueprint(app: Pint) -> None:
    blueprint = PintBlueprint('blueprint', __name__, url_prefix='/blueprint')

    @app.route('/testing')
    @blueprint.route('/testing')
    class Testing(Resource):
        async def get(self):
            return 'GET'

        async def post(self):
            return 'POST'

    app.register_blueprint(blueprint)

    client = app.test_client()
    response = await client.get('/openapi.json')
    assert response.status_code == HTTPStatus.OK

    openapi = await response.get_json()
    assert len(openapi['paths'].keys()) == 2

@pytest.mark.asyncio
async def test_openapi_blueprint_noprefix(app: Pint) -> None:
    blueprint = PintBlueprint('blueprint', __name__)

    @blueprint.route('/')
    class Testing(Resource):
        async def get(self):
            return 'GET'

    app.register_blueprint(blueprint)

    client = app.test_client()
    response = await client.get('/openapi.json')
    assert response.status_code == HTTPStatus.OK

    openapi = await response.get_json()
    assert openapi['paths'].get('/', None) is not None
    assert openapi['paths']['/'].get('get', None) is not None
