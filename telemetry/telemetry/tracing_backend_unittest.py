# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from telemetry import tab_test_case
from telemetry import util


class TracingBackendTest(tab_test_case.TabTestCase):
  def _StartServer(self):
    base_dir = os.path.dirname(__file__)
    self._browser.SetHTTPServerDirectory(os.path.join(base_dir, '..',
        'unittest_data'))

  def _WaitForAnimationFrame(self):
    def _IsDone():
      js_is_done = """done"""
      return bool(self._tab.EvaluateJavaScript(js_is_done))
    util.WaitFor(_IsDone, 5)

  def testGotTrace(self):
    self._StartServer()
    self._browser.StartTracing()
    self._browser.http_server.UrlOf('image.png')
    self.assertTrue(self._browser.supports_tracing)
    self._browser.StopTracing()
    trace = self._browser.GetTrace()
    json_trace = json.loads(trace)
    self.assertTrue('traceEvents' in json_trace)
    self.assertTrue(json_trace['traceEvents'])
