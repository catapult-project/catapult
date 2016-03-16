# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.testing import test_page_test_results
from telemetry.timeline import slice as slice_module
from telemetry.timeline import model as model_module
from telemetry.web_perf import timeline_interaction_record as tir_module

from telemetry.web_perf.metrics import v8_execution

RENDERER_PROCESS = 'Renderer'
OTHER_PROCESS = 'Other'
INTERACTION_RECORDS = [tir_module.TimelineInteractionRecord("test-record",
                                                            0,
                                                            float('inf'))]

STATS = ('v8_execution_time_total', 'v8_execution_time_self',
         'v8_parse_lazy_total', 'v8_compile_fullcode_total',
         'v8_recompile_total', 'v8_recompile_synchronous_total',
         'v8_recompile_concurrent_total', 'v8_optimize_code_total',
         'v8_deoptimize_code_total',)


class SliceContext(object):
  """
  Context object for easily adding subslices/subevents.
  """
  def __init__(self, test, record):
    self.test = test
    self.record = record

  def __enter__(self):
    self.test.parent_slice = self.record

  def __exit__(self, exc_type, exc_value, exc_traceback):
    self.test.parent_slice = self.record.parent_slice


class V8ExecutionTests(unittest.TestCase):

  def setUp(self):
    self.model = model_module.TimelineModel()
    self.renderer_process = self.model.GetOrCreateProcess(1)
    self.renderer_process.name = RENDERER_PROCESS
    self.renderer_thread = self.renderer_process.GetOrCreateThread(tid=11)
    self.other_process = self.model.GetOrCreateProcess(2)
    self.other_process.name = OTHER_PROCESS
    self.other_thread = self.other_process.GetOrCreateThread(tid=12)
    self.metric = v8_execution.V8ExecutionMetric()
    self.results = None
    self.parent_slice = None

  def GetThreadForProcessName(self, process_name):
    if process_name is RENDERER_PROCESS:
      return self.renderer_thread
    elif process_name is OTHER_PROCESS:
      return self.other_thread
    else:
      raise

  def AddResults(self):
    self.results = test_page_test_results.TestPageTestResults(self)
    self.metric.AddResults(self.model, self.renderer_thread,
                           INTERACTION_RECORDS, self.results)

  def AddEvent(self, process_name, event_category, event_name,
               start, duration, thread_start=None, thread_duration=None):
    thread = self.GetThreadForProcessName(process_name)
    record = slice_module.Slice(thread, event_category, event_name,
                start, duration,
                start if thread_start is None else thread_start,
                duration if thread_duration is None else thread_duration)
    thread.PushSlice(record)
    if self.parent_slice is not None:
      record.parent_slice = self.parent_slice
      self.parent_slice.AddSubSlice(record)
    return SliceContext(self, record)

  def AssertResultValues(self, name, value, count, average):
    self.results.AssertHasPageSpecificScalarValue('%s' % name, 'ms', value)
    self.results.AssertHasPageSpecificScalarValue('%s_count' % name, 'count',
                                                  count)
    self.results.AssertHasPageSpecificScalarValue('%s_average' % name, 'ms',
                                                  average)

  def testWithNoTraceEvents(self):
    self.AddResults()
    for name in STATS:
      self.AssertResultValues(name, value=0, count=0, average=0)

  def testExecutionTime(self):
    self.AddEvent(RENDERER_PROCESS, '', 'V8.Execute', 0, 10)
    with self.AddEvent(RENDERER_PROCESS, '', 'V8.Execute', 10, 20):
      self.AddEvent(RENDERER_PROCESS, '', 'other', 10, 12)
    self.AddResults()
    self.AssertResultValues('v8_execution_time_total', value=30, count=2,
                            average=15)
    self.AssertResultValues('v8_execution_time_self', value=18, count=2,
                            average=9)

  def testOptimizeParseLazy(self):
    self.AddEvent(RENDERER_PROCESS, '', 'V8.ParseLazy', 0, 10)
    self.AddResults()
    self.AssertResultValues('v8_parse_lazy_total', value=10, count=1,
                            average=10)
    self.AssertResultValues('v8_optimize_code_total', value=0, count=0,
                            average=0)
    self.AssertResultValues('v8_optimize_parse_lazy_total', value=0, count=0,
                            average=0)

    with self.AddEvent(RENDERER_PROCESS, '', 'V8.OptimizeCode', 10, 20):
      self.AddEvent(RENDERER_PROCESS, '', 'V8.ParseLazy', 20, 8)
    self.AddResults()
    self.AssertResultValues('v8_parse_lazy_total', value=18, count=2, average=9)
    self.AssertResultValues('v8_optimize_code_total', value=20, count=1,
                            average=20)
    self.AssertResultValues('v8_optimize_parse_lazy_total', value=8, count=1,
                            average=8)

  def testRecompile(self):
    self.AddEvent(RENDERER_PROCESS, '', 'V8.RecompileSynchronous', 0, 10)
    self.AddResults()
    self.AssertResultValues('v8_recompile_synchronous_total', value=10, count=1,
                            average=10)
    self.AssertResultValues('v8_recompile_concurrent_total', value=0, count=0,
                            average=0)
    self.AssertResultValues('v8_recompile_total', value=10, count=1, average=10)

    self.AddEvent(RENDERER_PROCESS, '', 'V8.RecompileConcurrent', 10, 8)
    self.AddResults()
    self.AssertResultValues('v8_recompile_synchronous_total', value=10, count=1,
                            average=10)
    self.AssertResultValues('v8_recompile_concurrent_total', value=8, count=1,
                            average=8)
    self.AssertResultValues('v8_recompile_total', value=18, count=2, average=9)
