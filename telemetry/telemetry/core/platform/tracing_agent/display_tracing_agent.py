# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import tracing_agent
from telemetry.timeline import trace_data


class DisplayTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(DisplayTracingAgent, self).__init__(platform_backend)

  @classmethod
  def IsSupported(cls, platform_backend):
    return platform_backend.IsDisplayTracingSupported()

  def Start(self, trace_options, category_filter, _timeout):
    if trace_options.enable_platform_display_trace:
      self._platform_backend.StartDisplayTracing()
      return True

  def Stop(self, trace_data_builder):
    surface_flinger_trace_data = self._platform_backend.StopDisplayTracing()
    trace_data_builder.AddEventsTo(
          trace_data.SURFACE_FLINGER_PART, surface_flinger_trace_data)
