# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from systrace.tracing_agents import atrace_agent
from telemetry.internal.platform import tracing_agent
from telemetry.timeline import trace_data

from devil.android.sdk import version_codes


class AtraceOpts(object):
  '''Object that holds Atrace options.

  In systrace, the atrace options are provided by an object generated
  by argparse. Since we're not using the command line options here and we
  want to hard-code the relevant options, we create an object here
  to do so.
  '''

  def __init__(self, serial_number, app_name):
    self.compress_trace_data = True
    self.trace_time = None
    self.trace_buf_size = None
    self.app_name = (','.join(app_name) if isinstance(app_name, list)
        else app_name)
    self.kfuncs = None
    self.fix_threads = True
    self.fix_tgids = True
    self.fix_circular = True
    self.device_serial_number = serial_number

class AtraceTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(AtraceTracingAgent, self).__init__(platform_backend)
    self._device = platform_backend.device
    self._categories = None
    self._atrace_agent = atrace_agent.AtraceAgent()
    self._options = None

  @classmethod
  def IsSupported(cls, platform_backend):
    return (platform_backend.GetOSName() == 'android' and
        platform_backend.device > version_codes.JELLY_BEAN_MR1)

  def StartAgentTracing(self, config, timeout):
    if not config.enable_atrace_trace:
      return False
    self._categories = config.atrace_config.categories
    self._options = AtraceOpts(str(self._device), config.atrace_config.app_name)
    return self._atrace_agent.StartAgentTracing(
        self._options, self._categories, timeout)

  def StopAgentTracing(self):
    self._atrace_agent.StopAgentTracing()

  def SupportsExplicitClockSync(self):
    # TODO(alexandermont): After bug
    # https://github.com/catapult-project/catapult/issues/2356 is fixed, change
    # this to return self._atrace_agent.SupportsExplicitClockSync.
    return False

  def RecordClockSyncMarker(self, sync_id,
                            record_controller_clock_sync_marker_callback):
    return self._atrace_agent.RecordClockSyncMarker(sync_id,
        lambda t, sid: record_controller_clock_sync_marker_callback(sid, t))

  def CollectAgentTraceData(self, trace_data_builder, timeout=None):
    raw_data = self._atrace_agent.GetResults(timeout).raw_data
    trace_data_builder.SetTraceFor(trace_data.ATRACE_PART, raw_data)
