# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.internal.results import page_test_results
from telemetry.internal.platform.tracing_agent import telemetry_tracing_agent
from tracing.trace_data import trace_data

from py_trace_event import trace_event


class FakeTraceDataBuilder(object):
  def __init__(self):
    """A fake trace bulder that just captures trace data written to it."""
    self._data = None

  def AddTraceFor(self, trace_part, data):
    assert self._data is None
    assert trace_part is trace_data.TELEMETRY_PART
    self._data = data

  def GetEventNames(self):
    return [e['name'] for e in self._data['traceEvents']]

  def GetTelemetryInfo(self):
    return self._data['metadata']['telemetry']


@unittest.skipUnless(trace_event.is_tracing_controllable(),
                     'py_trace_event is not supported')
class TelemetryTracingAgentTest(unittest.TestCase):
  def setUp(self):
    platform = None  # Does not actually need one.
    self.agent = telemetry_tracing_agent.TelemetryTracingAgent(platform)
    self.config = None  # Does not actually need one.

  def tearDown(self):
    if self.agent.is_tracing:
      self.agent.StopAgentTracing()

  def testAddTraceEvent(self):
    self.agent.StartAgentTracing(self.config, timeout=10)
    with trace_event.trace('test-marker'):
      pass
    self.agent.StopAgentTracing()
    trace = FakeTraceDataBuilder()
    self.agent.CollectAgentTraceData(trace)
    self.assertIn('test-marker', trace.GetEventNames())

  def testRecordClockSync(self):
    self.agent.StartAgentTracing(self.config, timeout=10)
    self.agent.RecordIssuerClockSyncMarker('1234', issue_ts=0)
    self.agent.StopAgentTracing()
    trace = FakeTraceDataBuilder()
    self.agent.CollectAgentTraceData(trace)
    self.assertIn('clock_sync', trace.GetEventNames())

  def testWriteTelemetryInfo(self):
    info = page_test_results.TelemetryInfo()
    info.benchmark_name = 'example'
    info.benchmark_start_epoch = 0

    self.agent.StartAgentTracing(self.config, timeout=10)
    self.agent.SetTelemetryInfo(info)
    self.agent.StopAgentTracing()
    trace = FakeTraceDataBuilder()
    self.agent.CollectAgentTraceData(trace)
    benchmarks = trace.GetTelemetryInfo()['benchmarks']
    self.assertEqual(len(benchmarks), 1)
    self.assertEqual(benchmarks[0], 'example')
