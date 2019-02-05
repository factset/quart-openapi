import pytest
from quart_openapi import Pint, Resource
from quart import jsonify
from http import HTTPStatus

@pytest.mark.asyncio
async def test_no_openapi():
    app = Pint('test', title='App Test', contact='foo',
               contact_email='moo@bar.com', no_openapi=True)
    client = app.test_client()
    rv = await client.get('/openapi.json')
    assert rv.status_code == HTTPStatus.NOT_FOUND

@pytest.mark.asyncio
async def test_custom_openapi():
    app = Pint('test', title='App Test', contact='foo', no_openapi=True,
               contact_email='moo@bar.com')

    @app.route('/hello')
    class Hello(Resource):
        async def get(self):
            return "OK"

    @app.route('/api.json', methods=['GET', 'OPTIONS'])
    async def api():
        return jsonify(app.__schema__)

    client = app.test_client()
    rv = await client.get('/api.json')
    assert rv.status_code == HTTPStatus.OK

    data = await rv.get_json()
    assert data == {'openapi': '3.0.0',
                    'info': {
                        'title': 'App Test',
                        'version': '1.0',
                        'contact': {
                            'name': 'foo',
                            'email': 'moo@bar.com'
                        }
                    },
                    'servers': [
                        {'url': 'http://'}
                    ],
                    'paths': {
                        '/hello': {
                            'get': {
                                'description': '', 'tags': [],
                                'responses': {
                                    '200': {
                                        'description': 'Success'
                                    }
                                },
                                'operationId': 'get_hello'
                            }
                        }
                    }
    }

