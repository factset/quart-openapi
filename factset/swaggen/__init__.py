# -*- coding: utf-8 -*-
from .resource import Resource
from .swaggen import SwagGen, SwaggerView
from .swagger import Swagger
from .__about__ import __short_version__, __description__, __release__

Resource.__module__ = __name__
SwagGen.__module__ = __name__
Swagger.__module__ = __name__

__all__ = [
    '__short_version__',
    '__description__',
    '__release__',
    'SwagGen',
    'Resource',
    'Swagger',
    'SwaggerView'
]
