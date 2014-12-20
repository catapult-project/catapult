# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import socket
import unittest
import urllib2

from telemetry.core.backends.chrome_inspector import devtools_http


_original_proxy_handler = urllib2.ProxyHandler

class DevToolsHttpTest(unittest.TestCase):

  def testUrlError(self):
    class FakeProxyHandler(object):
      def __init__(self, *_, **__):
        raise urllib2.URLError('Test')

    urllib2.ProxyHandler = FakeProxyHandler
    try:
      with self.assertRaises(devtools_http.DevToolsClientUrlError):
        devtools_http.DevToolsHttp(1000).Request('')
    finally:
      urllib2.ProxyHandler = _original_proxy_handler

  def testSocketError(self):
    class FakeProxyHandler(object):
      def __init__(self, *_, **__):
        raise socket.error

    urllib2.ProxyHandler = FakeProxyHandler
    try:
      with self.assertRaises(devtools_http.DevToolsClientConnectionError) as e:
        devtools_http.DevToolsHttp(1000).Request('')
      self.assertNotIsInstance(e, devtools_http.DevToolsClientUrlError)
    finally:
      urllib2.ProxyHandler = _original_proxy_handler

  def testBadStatusLine(self):
    class FakeProxyHandler(object):
      def __init__(self, *_, **__):
        raise httplib.BadStatusLine('Test')

    urllib2.ProxyHandler = FakeProxyHandler
    try:
      with self.assertRaises(devtools_http.DevToolsClientConnectionError) as e:
        devtools_http.DevToolsHttp(1000).Request('')
      self.assertNotIsInstance(e, devtools_http.DevToolsClientUrlError)
    finally:
      urllib2.ProxyHandler = _original_proxy_handler
