Installation
==================================================

Installation can be done in various ways. The simplest form uses pip
or easy_install. Either one will work::

    pip install rsa
    easy_install rsa

Depending on your system you may need to use ``sudo pip`` or ``sudo
easy_install``.

Installation from source is also quite easy. Download the source and
then type::

    python setup.py install

or if that doesn't work::

    sudo python setup.py install


The sources are tracked in our `Mercurial repository`_ at
bitbucket.org. It also hosts the `issue tracker`_.

.. _`Mercurial repository`: https://bitbucket.org/sybren/python-rsa
.. _`issue tracker`:
    https://bitbucket.org/sybren/python-rsa/issues?status=new&status=open


Dependencies
--------------------------------------------------

Python-RSA has very few dependencies. As a matter of fact, to use it
you only need Python itself. Loading and saving keys does require an
extra module, though: pyasn1. If you used pip or easy_install like
described above, you should be ready to go.


Development dependencies
--------------------------------------------------

In order to start developing on Python-RSA you need a bit more. Use
pip to install the development requirements in a virtual environment
for Python 2.x::

    virtualenv python-rsa-venv-py2x
    . python-rsa-venv-py2x/bin/activate
    pip install -r python-rsa/requirements-dev-py2x.txt

or Python 3.x::

    virtualenv python-rsa-venv-py3x
    . python-rsa-venv-py3x/bin/activate
    pip install -r python-rsa/requirements-dev-py3x.txt

Once these are installed, use Mercurial_ to get a copy of the source::

    hg clone https://bitbucket.org/sybren/python-rsa
    python setup.py develop

.. _Mercurial: http://hg-scm.com/
