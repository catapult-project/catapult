# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import StringIO

from telemetry.core import util
from telemetry.unittest import tab_test_case


class TabConsoleTest(tab_test_case.TabTestCase):
  def testConsoleOutputStream(self):
    stream = StringIO.StringIO()
    self._tab.message_output_stream = stream

    self.Navigate('page_that_logs_to_console.html')

    initial = self._tab.EvaluateJavaScript('window.__logCount')
    def GotLog():
      current = self._tab.EvaluateJavaScript('window.__logCount')
      return current > initial
    util.WaitFor(GotLog, 5)

    lines = [l for l in stream.getvalue().split('\n') if len(l)]

    self.assertTrue(len(lines) >= 1)
    for line in lines:
      prefix = 'http://(.+)/page_that_logs_to_console.html:9'
      expected_line = 'At %s: Hello, world' % prefix
      self.assertTrue(re.match(expected_line, line))
