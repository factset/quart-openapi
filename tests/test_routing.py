import pytest
from packaging import version
from quart_openapi import Pint, Resource
from jsonschema import RefResolver
from quart import request, jsonify, url_for
from quart.__about__ import __version__ as quart_version
from http import HTTPStatus

QUART_VER_GT_09 = version.parse(quart_version) >= version.parse('0.9.0')

def req_ctx(app: Pint, page: str, method: str=''):
    if QUART_VER_GT_09:
        return app.test_request_context(page, method=method)
    else:
        return app.test_request_context(method, page)

@pytest.mark.asyncio
async def test_simple_app(app):
    @app.route('/statusCheck')
    def status():
        return "OK"

    client = app.test_client()
    rv = await client.get('/statusCheck')
    assert rv.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_swagger_route(app):
    client = app.test_client()
    rv = await client.get('/openapi.json')
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_json()
    assert data['info']['title'] == 'App Test'
    assert data['info']['description'] == 'Sample Desc'
    assert data['info']['contact']['name'] == 'foo'
    assert data['info']['contact']['email'] == 'moo@bar.com'

@pytest.mark.asyncio
async def test_resource_get(app):
    @app.route('/testing')
    class Tester(Resource):
        async def get(self):
            return "Got"

    client = app.test_client()
    rv = await client.get('/testing')
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_data()
    assert data.decode('utf-8') == "Got"

@pytest.mark.asyncio
async def test_app_url_for(app):
    @app.route('/testing/')
    class Tester(Resource):
        async def get(self):
            return 'Got'

    async with req_ctx(app, '/', method='GET'):
        openapi_url = url_for('openapi')
        route_url = url_for('tester')
        assert '/openapi.json' == openapi_url
        assert '/testing/' == route_url

@pytest.mark.asyncio
async def test_resource_post(app):
    @app.route('/testing')
    class Tester(Resource):
        async def post(self):
            data = await request.get_json()
            return jsonify({ 'req': data, 'extra': 'foobar' })

    client = app.test_client()
    rv = await client.post('/testing', json={'moo': 'banana'})
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_json()
    assert len(data.keys()) == 2
    assert data['req'] == {'moo': 'banana'}
    assert data['extra'] == 'foobar'

@pytest.mark.asyncio
async def test_resource_default_route(app):
    @app.route('/route', defaults={'testing': 'bar'})
    @app.route('/route/<string:testing>')
    class Tester(Resource):
        async def get(self, testing):
            return testing

    client = app.test_client()
    rv = await client.get('/route/foo')
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_data()
    assert data == b'foo'

    rv = await client.get('/route')
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_data()
    assert data == b'bar'

@pytest.mark.asyncio
async def test_params(app):
    SWAGGER_RESP_OBJ = {
        'type': 'object',
        'properties': {
            'foobar': { 'type': 'string', 'description': 'the id' }
        }
    }
    resp = app.create_validator('response', SWAGGER_RESP_OBJ)

    @app.route('/<string:the_id>')
    @app.doc(params={'the_id': 'Test Id'})
    class Tester(Resource):
        @app.response(HTTPStatus.OK, 'Success', resp)
        async def get(self, the_id):
            """Test Get

            Testing the Description docs
            """
            return jsonify({'foobar': the_id})


    client = app.test_client()

    # test that the swagger has the info
    rv = await client.get('/openapi.json')
    assert rv.status_code == HTTPStatus.OK
    methods = [x.strip() for x in rv.headers['access-control-allow-methods'].split(',')]
    assert 'HEAD' in methods
    assert 'GET' in methods
    assert 'OPTIONS' in methods
    assert rv.headers['access-control-allow-origin'] == '*'

    swagger = await rv.get_json()
    assert len(swagger['paths'].keys()) == 1
    assert '/{the_id}' in swagger['paths']

    swag_path = swagger['paths']['/{the_id}']
    assert 'get' in swag_path
    assert swag_path['get']['description'] == 'Testing the Description docs'
    assert swag_path['get']['summary'] == 'Test Get'
    assert len(swag_path['get']['parameters']) == 1

    param_doc = swag_path['get']['parameters'][0]
    assert param_doc['name'] == 'the_id'
    assert param_doc['in'] == 'path'
    assert param_doc['required'] == True
    assert param_doc['schema'] == {'type': 'string'}
    assert param_doc['description'] == 'Test Id'

    resp_doc = swag_path['get']['responses']
    assert '200' in resp_doc
    assert resp_doc['200']['description'] == 'Success'
    assert resp_doc['200']['content']['application/json']['schema'] == SWAGGER_RESP_OBJ

    rv = await client.get('/baz')
    assert rv.status_code == HTTPStatus.OK
    data = await rv.get_json()
    assert data['foobar'] == 'baz'

TEST_BASE_MODEL_SCHEMA = {
    '$schema': 'http://json-schema.org/schema#',
    'id': 'schema.json',
    'components': {
        'schemas': {
            'User': {
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string'
                    },
                    'display': {
                        'type': 'string'
                    },
                    'age': {
                        'type': 'integer'
                    }
                },
                'required': ['name', 'age']
            }
        },
        'parameters': {
            'test_query': {
                'name': 'moo',
                'in': 'query',
                'required': True
            }
        },
        'requestBodies': {
            'User': {
                'content': {
                    'application/json': {
                        'schema': {
                            '$ref': '#/components/schemas/User'
                        }
                    },
                    'application/xml': {
                        'schema': {
                            '$ref': '#/components/schemas/User'
                        }
                    }
                }
            }
        }
    }
}

@pytest.mark.asyncio
async def test_base_model_obj():
    app = Pint('test', title='App Test', contact='foo',
                  contact_email='moo@bar.com', description='Sample Desc',
                  base_model_schema=TEST_BASE_MODEL_SCHEMA)

    @app.route('/testque')
    @app.param('test_que', ref='#/components/parameters/test_query')
    class TestQue(Resource):
        async def get(self):
            return request.args['moo']

    test_que_ref = app.create_ref_validator('test_query', 'parameters')

    @app.route('/testref')
    @app.param('test_que_ref', ref=test_que_ref)
    class TestRef(Resource):
        async def get(self):
            return request.args['moo']

    @app.route('/testquename')
    @app.param('test_que_name', ref='test_query')
    class TestQueName(Resource):
        async def get(self):
            return request.args['moo']

    swag = app.__schema__
    assert swag['components']['parameters']['test_query']['name'] == 'moo'
    swag_testque = swag['paths']['/testque']['get']
    swag_testref = swag['paths']['/testref']['get']
    swag_testquename = swag['paths']['/testquename']['get']
    assert swag_testque['parameters'] == swag_testref['parameters']
    assert swag_testque['parameters'] == swag_testquename['parameters']

    client = app.test_client()

    rv = await client.get('/testque?moo=foo')
    assert rv.status_code == HTTPStatus.OK
    assert await rv.get_data() == b'foo'

    rv = await client.get('/testref?moo=bar')
    assert rv.status_code == HTTPStatus.OK
    assert await rv.get_data() == b'bar'

    rv = await client.get('/testquename?moo=baz')
    assert rv.status_code == HTTPStatus.OK
    assert await rv.get_data() == b'baz'

@pytest.mark.asyncio
@pytest.mark.xfail
async def test_required_query():
    app = Pint('test', title='App Test', contact='foo',
                  contact_email='moo@bar.com', description='Sample Desc',
                  base_model_schema=TEST_BASE_MODEL_SCHEMA)

    test_que_ref = app.create_ref_validator('test_query', 'parameters')

    @app.param('test_que_ref', _in='query', schema=test_que_ref)
    @app.route('/testref')
    def testref():
        return request.args['moo']

    client = app.test_client()
    rv = await client.get('/testref')
    # will add validation in the future for required query args
    assert rv.status_code == HTTPStatus.BAD_REQUEST


def test_base_model_file(tmpdir):
    import json
    tmp_schema = tmpdir.join('schema.json')
    tmp_schema.write_text(json.dumps(TEST_BASE_MODEL_SCHEMA), encoding='utf-8')

    app = Pint('test', base_model_schema=str(tmp_schema.realpath()))

    assert isinstance(app.base_model, RefResolver)
    assert app.base_model.base_uri == 'schema.json'

def test_base_model_ref_resolve():
    base_model = RefResolver.from_schema(TEST_BASE_MODEL_SCHEMA)
    app = Pint('test', base_model_schema=base_model)

    assert isinstance(app.base_model, RefResolver)
    assert app.base_model.base_uri == 'schema.json'

@pytest.mark.asyncio
async def test_post_validation():
    app = Pint('test', base_model_schema=TEST_BASE_MODEL_SCHEMA)

    test_ref = app.create_ref_validator('User', 'schemas')

    @app.route('/testroute')
    class TestReq(Resource):
        @app.expect(test_ref)
        async def post(self):
            return jsonify(await request.get_json())

    client = app.test_client()

    # fail validation, missing required props
    rv = await client.post('/testroute', json={});
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert rv.headers['content-type'] == 'application/json'
    data = await rv.get_json()
    assert data['message'] == 'Request Body failed validation'
    assert 'msg' in data['error'] and data['error']['msg']
    assert 'value' in data['error']
    assert 'schema' in data['error']

    # fail validation, have required props, but age is wrong type
    rv = await client.post('/testroute', json={'name': 'foobar', 'age': 'baz'})
    assert rv.status_code == HTTPStatus.BAD_REQUEST
    assert rv.headers['content-type'] == 'application/json'
    data = await rv.get_json()
    assert data['message'] == 'Request Body failed validation'
    assert 'msg' in data['error'] and data['error']['msg']
    assert 'value' in data['error']
    assert 'schema' in data['error']

    # succeed validation
    rv = await client.post('/testroute', json={'name': 'foobar', 'age': 10})
    assert rv.status_code == HTTPStatus.OK

