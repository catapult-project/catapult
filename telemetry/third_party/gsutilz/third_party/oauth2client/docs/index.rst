oauth2client
============

*making OAuth2 just a little less painful*

``oauth2client`` makes it easy to interact with OAuth2-protected resources,
especially those related to Google APIs. You can also start with `general
information about using OAuth2 with Google APIs
<https://developers.google.com/accounts/docs/OAuth2>`_. 

Getting started
---------------

We recommend installing via ``pip``::

  $ pip install --upgrade oauth2client

You can also install from source::

  $ git clone https://github.com/google/oauth2client
  $ cd oauth2client
  $ python setup.py install

Downloads
^^^^^^^^^

* `Most recent release tarball
  <https://github.com/google/oauth2client/tarball/master>`_
* `Most recent release zipfile
  <https://github.com/google/oauth2client/zipball/master>`_
* `Complete release list <https://github.com/google/oauth2client/releases>`_ 

Library Documentation
---------------------

* Complete library index: :ref:`genindex`
* Index of all modules: :ref:`modindex`
* Search all documentation: :ref:`search`

Contributing
------------

Please see the `contributing page <contributing.html>`_ for more information.
In particular, we love pull requests -- but please make sure to sign the
contributor license agreement.

.. toctree::
   :maxdepth: 1
   :hidden:

   source/modules
   contributing

Supported Python Versions
-------------------------

We support Python 2.6, 2.7, 3.3+. (Whatever this file says, the truth is
always represented by our `tox.ini`_).

.. _tox.ini: https://github.com/google/oauth2client/blob/master/tox.ini

We explicitly decided to support Python 3 beginning with version
3.3. Reasons for this include:

* Encouraging use of newest versions of Python 3
* Following the lead of prominent `open-source projects`_
* Unicode literal support which
  allows for a cleaner codebase that works in both Python 2 and Python 3

.. _open-source projects: http://docs.python-requests.org/en/latest/
.. _Unicode literal support: https://www.python.org/dev/peps/pep-0414/
