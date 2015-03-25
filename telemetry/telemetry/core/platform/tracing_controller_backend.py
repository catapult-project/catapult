# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import discover
from telemetry.core.platform import tracing_agent
from telemetry.core.platform.tracing_agent import chrome_tracing_agent
from telemetry.core.platform.tracing_agent import display_tracing_agent
from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.core import util
from telemetry.timeline import trace_data as trace_data_module


def _IterAllTracingAgentClasses():
  tracing_agent_dir = os.path.join(
      os.path.dirname(os.path.realpath(__file__)), 'tracing_agent')
  return discover.DiscoverClasses(
      tracing_agent_dir, util.GetTelemetryDir(),
      tracing_agent.TracingAgent).itervalues()


class TracingControllerBackend(object):
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._current_trace_options = None
    self._current_category_filter = None
    self._current_chrome_tracing_agent = None
    self._current_display_tracing_agent = None
    self._supported_agents_classes = [
        agent_classes for agent_classes in _IterAllTracingAgentClasses() if
        agent_classes.IsSupported(platform_backend)]
    self._active_agents_instances = []

  def Start(self, trace_options, category_filter, timeout):
    if self.is_tracing_running:
      return False

    assert isinstance(category_filter,
                      tracing_category_filter.TracingCategoryFilter)
    assert isinstance(trace_options,
                      tracing_options.TracingOptions)
    assert len(self._active_agents_instances) == 0

    self._current_trace_options = trace_options
    self._current_category_filter = category_filter
    # Hack: chrome tracing agent depends on the number of alive chrome devtools
    # processes, rather platform, hence we add it to the list of supported
    # agents here if it was not added.
    if (chrome_tracing_agent.ChromeTracingAgent.IsSupported(
        self._platform_backend) and
        not chrome_tracing_agent.ChromeTracingAgent in
        self._supported_agents_classes):
      self._supported_agents_classes.append(
          chrome_tracing_agent.ChromeTracingAgent)

    for agent_class in self._supported_agents_classes:
      agent = agent_class(self._platform_backend)
      if agent.Start(trace_options, category_filter, timeout):
        self._active_agents_instances.append(agent)

  def Stop(self):
    assert self.is_tracing_running, 'Can only stop tracing when tracing.'
    trace_data_builder = trace_data_module.TraceDataBuilder()
    for agent in self._active_agents_instances:
      agent.Stop(trace_data_builder)
    self._active_agents_instances = []
    self._current_trace_options = None
    self._current_category_filter = None
    return trace_data_builder.AsData()

  def IsChromeTracingSupported(self):
    return chrome_tracing_agent.ChromeTracingAgent.IsSupported(
        self._platform_backend)

  @property
  def is_tracing_running(self):
    return self._current_trace_options != None
