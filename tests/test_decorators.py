import pytest
from quart_openapi import Pint, Resource
from http import HTTPStatus

@pytest.mark.asyncio
async def test_inheritance(app):
    @app.route('/hello')
    class Hello(Resource):
        async def get(self):
            return "hello"

    @app.route('/goodbye')
    class Goodbye(Hello):
        async def get(self):
            return "goodbye"

    client = app.test_client()
    rv = await client.get('/hello')
    assert rv.status_code == HTTPStatus.OK
    assert b"hello" == await rv.get_data()

    rv = await client.get('/goodbye')
    assert rv.status_code == HTTPStatus.OK
    assert b"goodbye" == await rv.get_data()
