"""quart-openapi

Quart-OpenAPI is an extension for Quart_ that adds support for generating a openapi.json file using openapi 3.0.
If you are familiar with Quart_, this just wraps around it to add a openapi.json route similar to Flask-RESTPlus_
generating a swagger.json route and adds a Resource base class for building RESTful APIs.

Documentation can be found on https://factset.github.io/quart-openapi/
"""

# -*- coding: utf-8 -*-
from .resource import Resource
from .pint import Pint, OpenApiView, PintBlueprint
from .swagger import Swagger
from .__about__ import __short_version__, __description__, __release__

# make sure that the module names for all of these are set to
# factset.quart_openapi instead of their individual files
Resource.__module__ = __name__
Pint.__module__ = __name__
PintBlueprint.__module__ = __name__
Swagger.__module__ = __name__

__all__ = [
    '__short_version__',
    '__description__',
    '__release__',
    'Pint',
    'PintBlueprint',
    'Resource',
    'Swagger',
    'OpenApiView'
]
