uritemplate
===========

.. image:: https://secure.travis-ci.org/uri-templates/uritemplate-py.png?branch=master
   :alt: build status
   :target: http://travis-ci.org/uri-templates/uritemplate-py

This is a Python implementation of `RFC6570`_, URI Template, and can
expand templates up to and including Level 4 in that specification.

It exposes a method, *expand*. For example:

.. code-block:: python

    >>> from uritemplate import expand
    >>> expand("http://www.{domain}/", {"domain": "foo.com"})
    'http://www.foo.com/'

It also exposes a method *variables* that returns all variables used in a
uritemplate. For example:

.. code-block:: python

    >>> from uritemplate import variables
    >>> variables('http:www{.domain*}{/top,next}{?q:20}')
    >>> set(['domain', 'next', 'q', 'top'])

This function can be useful to determine what keywords are available to be
expanded.

.. _RFC6570: http://tools.ietf.org/html/rfc6570


Requirements
------------

uritemplate works with Python 2.5+.

.. note:: You need to install `simplejson`_ module for Python 2.5.

.. _simplejson: https://pypi.python.org/pypi/simplejson/


Install
-------

The easiest way to install uritemplate is with pip::

    $ pip install uritemplate

See its `Python Package Index entry`_ for more.

.. _Python Package Index entry: http://pypi.python.org/pypi/uritemplate


License
=======

Copyright 2011-2013 Joe Gregorio

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
