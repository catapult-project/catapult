# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.backends.chrome_inspector import devtools_client_backend
from telemetry.core.backends.chrome_inspector import devtools_http
from telemetry.unittest_util import browser_test_case


class DevToolsClientBackendTest(browser_test_case.BrowserTestCase):
  @property
  def _devtools_client(self):
    return self._browser._browser_backend.devtools_client

  def testGetChromeBranchNumber(self):
    branch_num = self._devtools_client.GetChromeBranchNumber()
    self.assertIsInstance(branch_num, int)
    self.assertGreater(branch_num, 0)

  def testIsAlive(self):
    self.assertTrue(self._devtools_client.IsAlive())

  def testIsNotAlive(self):
    client = devtools_client_backend.DevToolsClientBackend(1000)
    def StubRequest(*_, **__):
      raise devtools_http.DevToolsClientConnectionError
    client._devtools_http.Request = StubRequest
    self.assertFalse(client.IsAlive())
