# pylint: disable=missing-module-docstring,missing-class-docstring
from http import HTTPStatus

import pytest
from quart_openapi import Resource

# pylint: disable=unused-variable,misplaced-comparison-constant,missing-function-docstring

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
