# pylint: disable=missing-module-docstring,missing-function-docstring
from quart.__about__ import __version__ as quart_version
from packaging import version
import pytest
from quart_openapi import Pint


QUART_VER_GT_09 = version.parse(quart_version) >= version.parse('0.9.0')

@pytest.fixture
def req_ctx():
    def func(testapp: Pint, page: str, method: str = ''):
        if QUART_VER_GT_09:
            return testapp.test_request_context(page, method=method)
        return testapp.test_request_context(method, page)
    return func

@pytest.fixture
def app():
    testapp = Pint('test', title='App Test', contact='foo',
                   contact_email='moo@bar.com', description='Sample Desc')
    return testapp
