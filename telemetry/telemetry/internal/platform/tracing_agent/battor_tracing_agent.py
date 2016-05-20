# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from battor import battor_error
from battor import battor_wrapper
from py_trace_event import trace_time
from telemetry.internal.platform import tracing_agent
from telemetry.timeline import trace_data


class BattOrTracingAgent(tracing_agent.TracingAgent):
  """A tracing agent for getting power data from a BattOr device.

  BattOrTracingAgent allows Telemetry to issue high-level tracing commands
  (StartTracing, StopTracing, RecordClockSyncMarker) to BattOrs, which are
  high-frequency power monitors used for battery testing.
  """

  def __init__(self, platform_backend):
    super(BattOrTracingAgent, self).__init__(platform_backend)
    self._platform_backend = platform_backend
    android_device = (
        platform_backend.device if platform_backend.GetOSName() == 'android'
        else None)
    self._battor = battor_wrapper.BattorWrapper(platform_backend.GetOSName(),
                                                android_device=android_device)

  @classmethod
  def IsSupported(cls, platform_backend):
    """Returns True if BattOr tracing is available."""
    if platform_backend.GetOSName() == 'android':
      # TODO(rnephew): When we pass BattOr device map into Telemetry, change
      # this to reflect that.
      return battor_wrapper.IsBattOrConnected(
          'android', android_device=platform_backend.device)
    return battor_wrapper.IsBattOrConnected(platform_backend.GetOSName())

  def StartAgentTracing(self, config, timeout):
    """Start tracing on the BattOr.

    Args:
      config: A TracingConfig instance.
      timeout: number of seconds that this tracing agent should try to start
        tracing until timing out.

    Returns:
      True if the tracing agent started successfully.
    """
    if not config.enable_battor_trace:
      return False
    try:
      self._battor.StartShell()
      self._battor.StartTracing()
      return True
    except battor_error.BattorError:
      logging.exception('Failure in starting tracing on BattOr.')
      return False

  def StopAgentTracing(self):
    """Stops tracing on the BattOr."""
    self._battor.StopTracing()

  def SupportsExplicitClockSync(self):
    return self._battor.SupportsExplicitClockSync()

  def RecordClockSyncMarker(self, sync_id,
                            record_controller_clock_sync_marker_callback):
    """Records a clock sync marker in the BattOr trace.

    Args:
      sync_id: Unique id for sync event.
      record_controller_clock_sync_marker_callback: Function that takes a sync
        ID and a timestamp as arguments. This function typically will record the
        tracing controller clock sync marker.
    """
    timestamp = trace_time.Now()
    self._battor.RecordClockSyncMarker(sync_id)
    record_controller_clock_sync_marker_callback(sync_id, timestamp)

  def CollectAgentTraceData(self, trace_data_builder, timeout=None):
    data = '\n'.join(self._battor.CollectTraceData(timeout=timeout))
    trace_data_builder.AddEventsTo(trace_data.BATTOR_TRACE_PART, [data])
