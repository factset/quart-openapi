#!/usr/bin/env python3

import os
import re
from setuptools import setup, find_packages

# Taken from flask-restplus setup.py

RE_REQUIREMENT = re.compile(r'^\s*-r\s*(?P<filename>.*)$')

PYPI_RST_FILTERS = (
    # Replace Python crossreferences by simple monospace
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`~(?:\w+\.)*(\w+)`', r'``\1``'),
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`([^`]+)`', r'``\1``'),
    # replace doc references
    (r':doc:`(.+) <(.*)>`', r'`\1 <http://flask-restplus.readthedocs.org/en/stable\2.html>`_'),
    # replace issues references
    (r':issue:`(.+?)`', r'`#\1 <https://github.com/noirbizarre/flask-restplus/issues/\1>`_'),
    # Drop unrecognized currentmodule
    (r'\.\. currentmodule:: .*', ''),
)

def rst(filename):
    '''
    Load rst file and sanitize it for PyPI.
    Remove unsupported github tags:
     - code-block directive
     - all badges
    '''
    content = open(filename).read()
    for regex, replacement in PYPI_RST_FILTERS:
        content = re.sub(regex, replacement, content)
    return content

def pip(filename):
    '''Parse pip reqs file and transform it to setuptools requirements.'''
    requirements = []
    with open(os.path.join('requirements', '{0}.pip'.format(filename))) as f:
        for line in f:
            line = line.strip()
            if not line or '://' in line or line.startswith('#'):
                continue
            requirements.append(line)
    return requirements

long_description = '\n'.join((
    rst('README.rst'),
    ''
))

exec(compile(open('fds/swaggen/__about__.py').read(), 'fds/swaggen/__about__.py', 'exec'))

install_requires = pip('install')
doc_require = pip('doc')

setup(
    name='fds-swaggen',
    version=__version__,
    description=__description__,
    long_description=long_description,
    url='<redacted>',
    author='Matt Topol',
    author_email='mtopol@factset.com',
    packages=find_packages(exclude=['tests', 'tests.*']),
    py_modules=['fds.swaggen'],
    install_requires=install_requires,
    extras_require={
        'doc': doc_require,
    },
    license='FactSet License',
    namespace_packages=['fds'],
    keywords='quart swagger api rest openapi'
)

