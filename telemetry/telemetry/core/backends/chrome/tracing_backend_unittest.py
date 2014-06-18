# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cStringIO
import json
import logging
import unittest

from telemetry.core import util
from telemetry.core.backends.chrome import tracing_backend
from telemetry.timeline import tracing_timeline_data
from telemetry.timeline.model import TimelineModel
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

    b = tracing_backend.CategoryFilter("disabled-by-default-test1")
    a = tracing_backend.CategoryFilter("disabled-by-default-test2")
    self.assertEquals(a.IsSubset(b), False)

  def testIsSubsetWithSyntheticDelays(self):
    b = tracing_backend.CategoryFilter("DELAY(foo;0.016)")
    a = tracing_backend.CategoryFilter("DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016)")
    a = tracing_backend.CategoryFilter(None)
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter(None)
    a = tracing_backend.CategoryFilter("DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016)")
    a = tracing_backend.CategoryFilter("DELAY(foo;0.032)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016;static)")
    a = tracing_backend.CategoryFilter("DELAY(foo;0.016;oneshot)")
    self.assertEquals(a.IsSubset(b), False)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_backend.CategoryFilter("DELAY(bar;0.1),DELAY(foo;0.016)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_backend.CategoryFilter("DELAY(bar;0.1)")
    self.assertEquals(a.IsSubset(b), True)

    b = tracing_backend.CategoryFilter("DELAY(foo;0.016),DELAY(bar;0.1)")
    a = tracing_backend.CategoryFilter("DELAY(foo;0.032),DELAY(bar;0.1)")
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
  def __init__(self, method_name):
    super(ChromeTraceResultTest, self).__init__(method_name)

  def testWrite1(self):
    ri = tracing_timeline_data.TracingTimelineData(map(json.loads, []))
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'], [])

  def testWrite2(self):
    ri = tracing_timeline_data.TracingTimelineData(map(json.loads, [
        '"foo"',
        '"bar"']))
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'], ['foo', 'bar'])

  def testWrite3(self):
    ri = tracing_timeline_data.TracingTimelineData(map(json.loads, [
        '"foo"',
        '"bar"',
        '"baz"']))
    f = cStringIO.StringIO()
    ri.Serialize(f)
    v = f.getvalue()

    j = json.loads(v)
    assert 'traceEvents' in j
    self.assertEquals(j['traceEvents'],
                      ['foo', 'bar', 'baz'])

  def testBrowserProcess(self):
    ri = tracing_timeline_data.TracingTimelineData(map(json.loads, [
        '{"name": "process_name",'
        '"args": {"name": "Browser"},'
        '"pid": 5, "ph": "M"}',
        '{"name": "thread_name",'
        '"args": {"name": "CrBrowserMain"},'
        '"pid": 5, "tid": 32578, "ph": "M"}']))
    model = TimelineModel(ri)
    self.assertEquals(model.browser_process.pid, 5)
