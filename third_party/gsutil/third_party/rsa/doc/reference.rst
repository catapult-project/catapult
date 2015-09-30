Reference
==================================================

This is the class and function reference. For more usage information
see the :ref:`usage` page.

Functions
--------------------------------------------------

.. autofunction:: rsa.encrypt

.. autofunction:: rsa.decrypt

.. autofunction:: rsa.sign

.. autofunction:: rsa.verify

.. autofunction:: rsa.newkeys(keysize)


Classes
--------------------------------------------------

.. autoclass:: rsa.PublicKey
    :members:
    :inherited-members:

.. autoclass:: rsa.PrivateKey
    :members:
    :inherited-members:

Exceptions
--------------------------------------------------

.. autoclass:: rsa.pkcs1.CryptoError(Exception)

.. autoclass:: rsa.pkcs1.DecryptionError(CryptoError)

.. autoclass:: rsa.pkcs1.VerificationError(CryptoError)


.. index:: VARBLOCK (file format)

Module: rsa.bigfile
--------------------------------------------------

The :py:mod:`rsa.bigfile` module contains functions for encrypting and
decrypting files that are larger than the RSA key. See
:ref:`bigfiles` for more information.

.. autofunction:: rsa.bigfile.encrypt_bigfile

.. autofunction:: rsa.bigfile.decrypt_bigfile

.. _VARBLOCK:

The VARBLOCK file format
++++++++++++++++++++++++++++++++++++++++++++++++++

The VARBLOCK file format allows us to encrypt files that are larger
than the RSA key. The format is as follows; || denotes byte string
concatenation::

 VARBLOCK := VERSION || BLOCK || BLOCK || ...

 VERSION := 1

 BLOCK := LENGTH || DATA

 LENGTH := varint-encoded length of the following data, in bytes

 DATA := the data to store in the block

The varint-format was taken from Google's Protobuf_, and allows us to
efficiently encode an arbitrarily long integer.

.. _Protobuf:
    http://code.google.com/apis/protocolbuffers/docs/encoding.html#varints


Module: rsa.core
--------------------------------------------------

At the core of the RSA encryption method lie these functions. They
both operate on (arbitrarily long) integers only. They probably aren't
of much use to you, but I wanted to document them anyway as they are
the core of the entire library.

.. autofunction:: rsa.core.encrypt_int

.. autofunction:: rsa.core.decrypt_int

