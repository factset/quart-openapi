=======
SwagGen
=======

.. inclusion-marker-do-not-remove

SwagGen is an extension for Quart_ that adds support for generating a swagger.json file using openapi 3.0.
If you are familiar with Quart, this just wraps around it to add a swagger.json route similar to Flask-RESTPlus_
and adds a Resource base class for building RESTful APIs.

.. _Quart: https://pgjones.gitlab.io/quart/
.. _Flask-RESTPlus: https://flask-restplus.readthedocs.io/en/stable/

Compatibility
=============

SwagGen requires Python 3.6+ because Quart_ requires it.

Installation
============

You can install via pip

.. code-block:: console

    $ pip install factset.swaggen
