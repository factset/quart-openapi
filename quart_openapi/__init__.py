# -*- coding: utf-8 -*-
from .resource import Resource
from .pint import Pint, SwaggerView, PintBlueprint
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
    'SwaggerView'
]
