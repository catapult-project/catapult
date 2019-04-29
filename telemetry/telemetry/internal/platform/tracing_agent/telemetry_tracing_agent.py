# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import tempfile

from telemetry.internal.platform import tracing_agent
from tracing.trace_data import trace_data

from py_trace_event import trace_event


def IsAgentEnabled():
  """Returns True if the agent is currently enabled and tracing."""
  return trace_event.trace_is_enabled()


def SetTelemetryInfo(telemetry_info):
  """Record Telemetry metadata if tracing is enabled."""
  if IsAgentEnabled():
    trace_event.trace_add_metadata({
        # TODO(crbug.com/948633): For right now, we use "TELEMETRY" as the
        # clock domain to guarantee that Telemetry is given its own clock
        # domain. Telemetry isn't really a clock domain, though: it's a
        # system that USES a clock domain like LINUX_CLOCK_MONOTONIC or
        # WIN_QPC. However, there's a chance that a Telemetry controller
        # running on Linux (using LINUX_CLOCK_MONOTONIC) is interacting
        # with an Android phone (also using LINUX_CLOCK_MONOTONIC, but
        # on a different machine). The current logic collapses clock
        # domains based solely on the clock domain string, but we really
        # should to collapse based on some (device ID, clock domain ID)
        # tuple. Giving Telemetry its own clock domain is a work-around
        # for this.
        'clock-domain': 'TELEMETRY',
        'telemetry': telemetry_info.AsDict(),
    })
  else:
    logging.warning(
        'Telemetry tracing agent is not enabled. Discarding Telemetry info.')


def RecordIssuerClockSyncMarker(sync_id, issue_ts):
  """Record clock sync event.

  Args:
    sync_id: Unique id for sync event.
    issue_ts: timestamp before issuing clock sync to agent.
  """
  trace_event.clock_sync(sync_id, issue_ts=issue_ts)


class TelemetryTracingAgent(tracing_agent.TracingAgent):
  """Tracing agent to collect data about Telemetry (and Python) execution.

  Is implemented as a thin wrapper around py_trace_event.trace_event. Clients
  can record events using the trace_event.trace() decorator or the
  trace_event.TracedMetaClass to trace all methods of a class.

  Also works as the clock sync recorder, against which other tracing agents
  can issue clock sync events. And is responsible for recording telemetry
  metadata with information e.g. about the benchmark that produced a trace.
  """
  def __init__(self, platform_backend):
    super(TelemetryTracingAgent, self).__init__(platform_backend)
    self._trace_file = None

  @classmethod
  def IsSupported(cls, platform_backend):
    del platform_backend  # Unused.
    return trace_event.is_tracing_controllable()

  @property
  def is_tracing(self):
    return IsAgentEnabled()

  def StartAgentTracing(self, config, timeout):
    del config  # Unused.
    del timeout  # Unused.
    assert not self.is_tracing, 'Telemetry tracing already running'

    # Create a temporary file and pass the opened file-like object to
    # trace_event.trace_enable(); the file will be closed on trace_disable(),
    # and later passed to a trace data builder in CollectAgentTraceData().
    self._trace_file = tempfile.NamedTemporaryFile(delete=False)
    trace_event.trace_enable(
        self._trace_file, format=trace_event.JSON_WITH_METADATA)
    assert self.is_tracing, 'Failed to start Telemetry tracing'
    return True

  def StopAgentTracing(self):
    assert self.is_tracing, 'Telemetry tracing is not running'
    trace_event.trace_disable()
    assert not self.is_tracing, 'Failed to stop Telemetry tracing'

  def CollectAgentTraceData(self, trace_data_builder, timeout=None):
    assert not self.is_tracing, 'Must stop tracing before collection'
    assert self._trace_file.closed, 'Trace file was not properly closed'
    # Ownership of the file, and responsibility to manage its lifetime, is now
    # transferred over to the trace data builder.
    trace_data_builder.AddTraceFileFor(
        trace_data.TELEMETRY_PART, self._trace_file.name)
    self._trace_file = None
