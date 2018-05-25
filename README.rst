=======
SwagGen
=======

.. inclusion-marker-do-not-remove

SwagGen is an extension for Quart_ that adds support for generating a swagger.json file using openapi 3.0.
If you are familiar with Quart_, this just wraps around it to add a swagger.json route similar to Flask-RESTPlus_
and adds a Resource base class for building RESTful APIs.

Compatibility
=============

SwagGen requires Python 3.6+ because Quart_ requires it.

Installation
============

You can install via pip

.. code-block:: console

    $ pip install factset.swaggen

If you are developing the module and want to also be able to build the documentation, make sure
to also install the dependencies from the extras 'doc' package like so:

.. code-block:: console

    $ pip install 'factset.swaggen[doc]'
    $ python setup.py build_sphinx

Quick Start
===========

If you're familiar with Quart_ then the quick start doesn't change much:

.. code-block:: python

    from factset.swaggen import SwagGen, Resource

    app = SwagGen(__name__, title='Sample App')

    @app.route('/')
    class Root(Resource):
      async def get(self):
        '''Hello World Route

        This docstring will show up as the description and short-description
        for the swagger docs for this route.
        '''
        return "hello"


This is equivalent to using the following with Quart_ as normal:

.. code-block:: python

    from quart import Quart
    app = Quart(__name__)

    @app.route('/')
    async def hello():
      return "hello"

Except that by using :py:class:`~factset.swaggen.SwagGen` and :py:class:`~factset.swaggen.Resource` it will also
add a route for '/swagger.json' which will contain the documentation of the route and use the docstring for the
description.

.. _Quart: https://pgjones.gitlab.io/quart/
.. _Flask-RESTPlus: https://flask-restplus.readthedocs.io/en/stable/
