# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import StringIO

from telemetry import tab_test_case
from telemetry import util

class TabConsoleTest(tab_test_case.TabTestCase):
  def testConsoleOutputStream(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     '..', 'unittest_data')
    self._browser.SetHTTPServerDirectory(unittest_data_dir)

    stream = StringIO.StringIO()
    self._tab.message_output_stream = stream

    self._tab.page.Navigate(
      self._browser.http_server.UrlOf('page_that_logs_to_console.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

    initial = self._tab.runtime.Evaluate('window.__logCount')
    def GotLog():
      current = self._tab.runtime.Evaluate('window.__logCount')
      return current > initial
    util.WaitFor(GotLog, 5)

    lines = [l for l in stream.getvalue().split('\n') if len(l)]

    self.assertTrue(len(lines) >= 1)
    for l in lines:
      u_l = 'http://localhost:(\d+)/page_that_logs_to_console.html:9'
      self.assertTrue(re.match('At %s: Hello, world' % u_l, l))

