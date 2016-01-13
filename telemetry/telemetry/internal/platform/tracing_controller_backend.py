# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
import traceback

from telemetry.core import discover
from telemetry.core import util
from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform.tracing_agent import chrome_tracing_agent
from telemetry.timeline import trace_data as trace_data_module
from telemetry.timeline import tracing_config


def _IterAllTracingAgentClasses():
  tracing_agent_dir = os.path.join(
      os.path.dirname(os.path.realpath(__file__)), 'tracing_agent')
  return discover.DiscoverClasses(
      tracing_agent_dir, util.GetTelemetryDir(),
      tracing_agent.TracingAgent).itervalues()


class TracingControllerStoppedError(Exception):
  pass


class TracingControllerBackend(object):
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._current_chrome_tracing_agent = None
    self._current_config = None
    self._supported_agents_classes = [
        agent_classes for agent_classes in _IterAllTracingAgentClasses() if
        agent_classes.IsSupported(platform_backend)]
    self._active_agents_instances = []

  def Start(self, config, timeout):
    if self.is_tracing_running:
      return False

    assert isinstance(config, tracing_config.TracingConfig)
    assert len(self._active_agents_instances) == 0

    self._current_config = config
    # Hack: chrome tracing agent may only depend on the number of alive chrome
    # devtools processes, rather platform (when startup tracing is not
    # supported), hence we add it to the list of supported agents here if it was
    # not added.
    if (chrome_tracing_agent.ChromeTracingAgent.IsSupported(
        self._platform_backend) and
        not chrome_tracing_agent.ChromeTracingAgent in
        self._supported_agents_classes):
      self._supported_agents_classes.append(
          chrome_tracing_agent.ChromeTracingAgent)

    for agent_class in self._supported_agents_classes:
      agent = agent_class(self._platform_backend)
      if agent.Start(config, timeout):
        self._active_agents_instances.append(agent)

  def Stop(self):
    assert self.is_tracing_running, 'Can only stop tracing when tracing is on.'
    trace_data_builder = trace_data_module.TraceDataBuilder()

    raised_execption_messages = []
    for agent in self._active_agents_instances:
      try:
        agent.Stop(trace_data_builder)
      except Exception:
        raised_execption_messages.append(
            ''.join(traceback.format_exception(*sys.exc_info())))

    self._active_agents_instances = []
    self._current_config = None

    if raised_execption_messages:
      raise TracingControllerStoppedError(
          'Exceptions raised when trying to stop tracing:\n' +
          '\n'.join(raised_execption_messages))

    return trace_data_builder.AsData()

  def IsChromeTracingSupported(self):
    return chrome_tracing_agent.ChromeTracingAgent.IsSupported(
        self._platform_backend)

  @property
  def is_tracing_running(self):
    return self._current_config != None

  def _GetActiveChromeTracingAgent(self):
    if not self.is_tracing_running:
      return None
    if not self._current_config.tracing_options.enable_chrome_trace:
      return None
    for agent in self._active_agents_instances:
      if isinstance(agent, chrome_tracing_agent.ChromeTracingAgent):
        return agent
    return None

  def GetChromeTraceConfig(self):
    agent = self._GetActiveChromeTracingAgent()
    if agent:
      return agent.trace_config
    return None

  def GetChromeTraceConfigFile(self):
    agent = self._GetActiveChromeTracingAgent()
    if agent:
      return agent.trace_config_file
    return None
