# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import logging
import unittest

from telemetry.core import util
from telemetry.core.backends.chrome import tracing_backend
from telemetry.unittest import tab_test_case

class CategoryFilterTest(unittest.TestCase):
  def testIsSubset(self):
    b = tracing_backend.CategoryFilter(None)
    a = tracing_backend.CategoryFilter(None)
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter(None)
    a = tracing_backend.CategoryFilter("test1,test2")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter(None)
    a = tracing_backend.CategoryFilter("-test1,-test2")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter("test1,test2")
    a = tracing_backend.CategoryFilter(None)
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_backend.CategoryFilter(None)
    a = tracing_backend.CategoryFilter("test*")
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_backend.CategoryFilter("test?")
    a = tracing_backend.CategoryFilter(None)
    self.assertEquals(a.IsSubset(b), None)

    b = tracing_backend.CategoryFilter("test1")
    a = tracing_backend.CategoryFilter("test1,test2")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("-test1")
    a = tracing_backend.CategoryFilter("test1")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("test1,test2")
    a = tracing_backend.CategoryFilter("test2,test1")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter("-test1,-test2")
    a = tracing_backend.CategoryFilter("-test2")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("disabled-by-default-test1")
    a = tracing_backend.CategoryFilter(
        "disabled-by-default-test1,disabled-by-default-test2")
    self.assertEquals(a.IsSubset(b), False)

class TracingBackendTest(tab_test_case.TabTestCase):
  def _StartServer(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())

  def _WaitForAnimationFrame(self):
    def _IsDone():
      js_is_done = """done"""
      return bool(self._tab.EvaluateJavaScript(js_is_done))
    util.WaitFor(_IsDone, 5)

  def testGotTrace(self):
    if not self._browser.supports_tracing:
      logging.warning('Browser does not support tracing, skipping test.')
      return
    self._StartServer()
    self._browser.StartTracing()
    self._browser.StopTracing()

    # TODO(tengs): check model for correctness after trace_event_importer
    # is implemented (crbug.com/173327).


class ChromeTraceResultTest(unittest.TestCase):
  # Override TestCase.run to run a test with all possible
  # implementations of ChromeTraceResult.
  def __init__(self, method_name):
    self._chromeTraceResultClass = None
    super(ChromeTraceResultTest, self).__init__(method_name)

  def run(self, result=None):
    def ChromeRawTraceResultWrapper(strings):
      return tracing_backend.ChromeRawTraceResult(map(json.loads, strings))
    classes = [
        tracing_backend.ChromeLegacyTraceResult,
        ChromeRawTraceResultWrapper
    ]
    for cls in classes:
      self._chromeTraceResultClass = cls
      super(ChromeTraceResultTest, self).run(result)

  def testWrite1(self):
    ri = self._chromeTraceResultClass([])
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'], [])

  def testWrite2(self):
    ri = self._chromeTraceResultClass([
        '"foo"',
        '"bar"'])
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'], ['foo', 'bar'])

  def testWrite3(self):
    ri = self._chromeTraceResultClass([
        '"foo"',
        '"bar"',
        '"baz"'])
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'],
                      ['foo', 'bar', 'baz'])
