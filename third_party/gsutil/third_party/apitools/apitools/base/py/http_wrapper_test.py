"""Tests for http_wrapper."""
import unittest2

from apitools.base.py import http_wrapper


class RaisesExceptionOnLen(object):

    """Supports length property but raises if __len__ is used."""

    def __len__(self):
        raise Exception('len() called unnecessarily')

    def length(self):
        return 1


class HttpWrapperTest(unittest2.TestCase):

    def testRequestBodyUsesLengthProperty(self):
        http_wrapper.Request(body=RaisesExceptionOnLen())

    def testRequestBodyWithLen(self):
        http_wrapper.Request(body='burrito')
