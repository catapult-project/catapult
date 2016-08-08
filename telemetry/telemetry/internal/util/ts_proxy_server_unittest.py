# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.util import ts_proxy_server

class TsProxyServerTest(unittest.TestCase):
  def testParseTsProxyPort(self):
    self.assertEquals(
      ts_proxy_server.ParseTsProxyPortFromOutput(
          'Started Socks5 proxy server on 127.0.0.1:54430 \n'),
      54430)
    self.assertEquals(
      ts_proxy_server.ParseTsProxyPortFromOutput(
          'Started Socks5 proxy server on foo.bar.com:430 \n'),
      430)
    self.assertEquals(
      ts_proxy_server.ParseTsProxyPortFromOutput(
          'Failed to start sock5 proxy.'),
      None)

  def testSmoke(self):
    with ts_proxy_server.TsProxyServer(37124, 37125) as server:
      self.assertIsNotNone(server.port)
