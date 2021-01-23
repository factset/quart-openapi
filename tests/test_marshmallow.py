# pylint: disable=missing-module-docstring,missing-class-docstring
from http import HTTPStatus

import pytest
from quart import jsonify, request
from marshmallow import Schema, fields

from quart_openapi import Resource

# pylint: disable=unused-variable,misplaced-comparison-constant,missing-function-docstring


@pytest.mark.asyncio
async def test_expect(app):
    class TestSchema(Schema):
        name = fields.String()

    @app.route('/')
    class Tester(Resource):
        @app.expect(TestSchema())
        async def post(self):
            """Test Post"""
            data = await request.get_json()
            return jsonify(data), HTTPStatus.CREATED

    client = app.test_client()

    name = 'test'
    rv = await client.post('/', json={'name': name})
    assert rv.status_code == HTTPStatus.CREATED
    assert (await rv.get_json()) == {'name': name}


@pytest.mark.asyncio
async def test_not_expect(app):
    class TestSchema(Schema):
        name = fields.String()

    @app.route('/')
    class Tester(Resource):
        @app.expect(TestSchema())
        async def post(self):
            """Test Post"""
            data = await request.get_json()
            return jsonify(data), HTTPStatus.CREATED

    client = app.test_client()

    rv = await client.post('/', json={'foo': 'name'})
    assert rv.status_code == HTTPStatus.BAD_REQUEST
