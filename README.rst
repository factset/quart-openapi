=============
Quart-OpenAPI  
=============

.. image:: https://travis-ci.com/factset/quart-openapi.svg?branch=master
   :target: https://travis-ci.com/factset/quart-openapi

Documentation can be found on https://factset.github.io/quart-openapi/

.. inclusion-marker-do-not-remove

Quart-OpenAPI is an extension for Quart_ that adds support for generating a openapi.json file using openapi 3.0.
If you are familiar with Quart_, this just wraps around it to add a openapi.json route similar to Flask-RESTPlus_
generating a swagger.json route and adds a Resource base class for building RESTful APIs.

Compatibility
=============

Quart-OpenAPI requires Python 3.6+ because Quart_ requires it.

Installation
============

You can install via pip

.. code-block:: console

    $ pip install quart-openapi

If you are developing the module and want to also be able to build the documentation, make sure
to also install the dependencies from the extras 'doc' package like so:

.. code-block:: console

    $ pip install 'quart-openapi[doc]'
    $ python setup.py build_sphinx

Quick Start
===========

If you're familiar with Quart_ then the quick start doesn't change much:

.. code-block:: python

    from quart_openapi import Pint, Resource

    app = Pint(__name__, title='Sample App')

    @app.route('/')
    class Root(Resource):
      async def get(self):
        '''Hello World Route

        This docstring will show up as the description and short-description
        for the openapi docs for this route.
        '''
        return "hello"


This is equivalent to using the following with Quart_ as normal:

.. code-block:: python

    from quart import Quart
    app = Quart(__name__)

    @app.route('/')
    async def hello():
      return "hello"

Except that by using :class:`~quart_openapi.Pint` and :class:`~quart_openapi.Resource` it will also
add a route for '/openapi.json' which will contain the documentation of the route and use the docstring for the
description.

Unit Tests
==========

Unit tests can be run through setuptools also:

.. code-block:: console

    $ python setup.py test

Request Validation
==================

Request validation like you can get with Flask-RESTPlus_!

You can either create validator models on the fly or you can create a jsonschema document for base models
and then use references to it. For an on-the-fly validator:

.. code-block:: python

    expected = app.create_validator('sample_request', {
      'type': 'object',
      'properties': {
        'foobar': {
          'type': 'string'
        },
        'baz': {
          'oneOf': [
            { 'type': 'integer' },
            { 'type': 'number', 'format': 'float' }
          ]
        }
      }
    })

    @app.route('/')
    class Sample(Resource):
      @app.expect(expected)
      async def post(self):
        # won't get here if the request didn't match the expected schema
        data = await request.get_json()
        return jsonify(data)


The default content type is 'application/json', but you can specify otherwise in the decorator:

.. code-block:: json
   :caption: schema.json

   {
     "$schema": "http://json-schema.org/schema#",
     "id": "schema.json",
     "components": {
       "schemas": {
         "binaryData": {
           "type": "string",
           "format": "binary"
         }
       }
     }
   }

.. code-block:: python
   :caption: app.py

   app = Pint(__name__, title='Validation Example',
                 base_model_schema='schema.json')
   stream = app.create_ref_validator('binaryData', 'schemas')

   @app.route('/')
   class Binary(Resource):
     @app.expect((stream, 'application/octet-stream',
                  {'description': 'gzip compressed data'}))
     @app.response(HTTPStatus.OK, 'Success')
     async def post(self):
       # if the request didn't have a 'content-type' header with a value
       # of 'application/octet-stream' it will be rejected as invalid.
       raw_data = await request.get_data(raw=True)
       # ... do something with the data
       return "Success!"

In the example above, it'll open, read, and json parse the file *schema.json* and then use it as the basis
for referencing models and creating validators. Currently the validator won't do more than validate content-type
for content-types other than 'application/json'.

.. _Quart: https://pgjones.gitlab.io/quart/
.. _Flask-RESTPlus: https://flask-restplus.readthedocs.io/en/stable/
