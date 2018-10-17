import pytest
from quart_openapi import Pint

@pytest.fixture
def app():
    app = Pint('test', title='App Test', contact='foo',
                  contact_email='moo@bar.com', description='Sample Desc')
    return app
