# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform.tracing_agent import (
    chrome_devtools_tracing_backend)


class ChromeTracingAgent(tracing_agent.TracingAgent):
  def __init__(self, platform_backend):
    super(ChromeTracingAgent, self).__init__(platform_backend)
    self._chrome_devtools_tracing_backend = (
      chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend(
        platform_backend))

  @classmethod
  def RegisterDevToolsClient(cls, devtools_client_backend, platform_backend):
    (chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend
        .RegisterDevToolsClient(devtools_client_backend, platform_backend))

  @classmethod
  def IsSupported(cls, platform_backend):
    return (chrome_devtools_tracing_backend.ChromeDevtoolsTracingBackend
      .IsSupported(platform_backend))

  def Start(self, trace_options, category_filter, timeout):
    return self._chrome_devtools_tracing_backend.Start(
        trace_options, category_filter, timeout)

  def Stop(self, trace_data_builder):
    self._chrome_devtools_tracing_backend.Stop(trace_data_builder)
