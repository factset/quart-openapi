#!/usr/bin/env python3

import os
import re
from setuptools import setup

# Based on flask-restplus setup.py

RE_REQUIREMENT = re.compile(r'^\s*-r\s*(?P<filename>.*)$')

PYPI_RST_FILTERS = (
    # Replace Python crossreferences by simple monospace
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`~(?:\w+\.)*(\w+)`', r'``\1``'),
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`([^`]+)`', r'``\1``'),
    # Drop unrecognized currentmodule
    (r'\.\. currentmodule:: .*', ''),
    # Drop caption tag
    (r'\s+:caption: .*', r''),
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

exec(compile(open('quart_openapi/__about__.py').read(), 'quart_openapi/__about__.py', 'exec'))

install_requires = pip('install')
doc_require = pip('doc')
setup_requires = pip('setup')
tests_require = pip('test')

try:
    from sphinx.setup_command import BuildDoc
    sphinx_opts = {'cmdclass': {'build_sphinx': BuildDoc},
                   'command_options': {
                       'build_sphinx': {
                           'version': ('setup.py', __short_version__),
                           'release': ('setup.py', __release__)}}}
except ImportError:
    sphinx_opts = {}

setup(
    name='quart-openapi',
    version=__release__,
    description=__description__,
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/factset/quart-openapi',
    author='Matt Topol',
    author_email='mtopol@factset.com',
    packages=['quart_openapi'],
    include_package_data=True,
    install_requires=install_requires,
    setup_requires=setup_requires,
    tests_require=tests_require,
    python_requires='>=3.6',
    license='Apache 2.0',
    keywords='quart swagger api rest openapi flask',
    extras_require={
        'doc': doc_require
    },
    classifiers=(
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Environment :: Web Environment',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ),
    **sphinx_opts
)

