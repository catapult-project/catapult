# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import atexit
import contextlib
import gc
import logging
import os
import sys
import tempfile
import traceback
import uuid

from py_trace_event import trace_event
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


class _TracingState(object):

  def __init__(self, config, timeout):
    self._builder = trace_data_module.TraceDataBuilder()
    self._config = config
    self._timeout = timeout

  @property
  def builder(self):
    return self._builder

  @property
  def config(self):
    return self._config

  @property
  def timeout(self):
    return self._timeout


class TracingControllerBackend(object):
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._current_state = None
    self._supported_agents_classes = [
        agent_classes for agent_classes in _IterAllTracingAgentClasses() if
        agent_classes.IsSupported(platform_backend)]
    self._active_agents_instances = []
    self._trace_log = None
    self._is_tracing_controllable = True

  def StartTracing(self, config, timeout):
    if self.is_tracing_running:
      return False

    assert isinstance(config, tracing_config.TracingConfig)
    assert len(self._active_agents_instances) == 0

    self._current_state = _TracingState(config, timeout)
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

    self.StartAgentTracing(config, timeout)
    for agent_class in self._supported_agents_classes:
      agent = agent_class(self._platform_backend)
      if agent.StartAgentTracing(config, timeout):
        self._active_agents_instances.append(agent)
    return True

  def _GenerateClockSyncId(self):
    return str(uuid.uuid4())

  @contextlib.contextmanager
  def _DisableGarbageCollection(self):
    try:
      gc.disable()
      yield
    finally:
      gc.enable()

  def StopTracing(self):
    assert self.is_tracing_running, 'Can only stop tracing when tracing is on.'
    self._IssueClockSyncMarker()
    builder = self._current_state.builder

    raised_exception_messages = []
    for agent in self._active_agents_instances + [self]:
      try:
        agent.StopAgentTracing(builder)
      except Exception: # pylint: disable=broad-except
        raised_exception_messages.append(
            ''.join(traceback.format_exception(*sys.exc_info())))

    self._active_agents_instances = []
    self._current_state = None

    if raised_exception_messages:
      raise TracingControllerStoppedError(
          'Exceptions raised when trying to stop tracing:\n' +
          '\n'.join(raised_exception_messages))

    return builder.AsData()

  def FlushTracing(self):
    assert self.is_tracing_running, 'Can only flush tracing when tracing is on.'
    self._IssueClockSyncMarker()

    raised_exception_messages = []
    # Flushing the controller's pytrace is not supported.
    for agent in self._active_agents_instances:
      try:
        if agent.SupportsFlushingAgentTracing():
          agent.FlushAgentTracing(self._current_state.config,
                                  self._current_state.timeout,
                                  self._current_state.builder)
      except Exception: # pylint: disable=broad-except
        raised_exception_messages.append(
            ''.join(traceback.format_exception(*sys.exc_info())))

    if raised_exception_messages:
      raise TracingControllerStoppedError(
          'Exceptions raised when trying to stop tracing:\n' +
          '\n'.join(raised_exception_messages))

  def StartAgentTracing(self, config, timeout):
    self._is_tracing_controllable = self._IsTracingControllable()
    if not self._is_tracing_controllable:
      return False

    tf = tempfile.NamedTemporaryFile(delete=False)
    self._trace_log = tf.name
    tf.close()
    del config # unused
    del timeout # unused
    assert not trace_event.trace_is_enabled(), 'Tracing already running.'
    trace_event.trace_enable(self._trace_log)
    assert trace_event.trace_is_enabled(), 'Tracing didn\'t enable properly.'
    return True

  def StopAgentTracing(self, trace_data_builder):
    if not self._is_tracing_controllable:
      return
    assert trace_event.trace_is_enabled(), 'Tracing not running'
    trace_event.trace_disable()
    assert not trace_event.trace_is_enabled(), 'Tracing didnt disable properly.'
    with open(self._trace_log, 'r') as fp:
      data = ast.literal_eval(fp.read() + ']')
    trace_data_builder.AddEventsTo(trace_data_module.TELEMETRY_PART, data)
    try:
      os.remove(self._trace_log)
      self._trace_log = None
    except OSError:
      logging.exception('Error when deleting %s, will try again at exit.',
                        self._trace_log)
      def DeleteAtExit(path):
        os.remove(path)
      atexit.register(DeleteAtExit, self._trace_log)
    self._trace_log = None

  def SupportsExplicitClockSync(self):
    return True

  def _RecordIssuerClockSyncMarker(self, sync_id, issue_ts):
    """ Record clock sync event.

    Args:
      sync_id: Unqiue id for sync event.
      issue_ts: timestamp before issuing clocksync to agent.
    """
    if self._is_tracing_controllable:
      trace_event.clock_sync(sync_id, issue_ts=issue_ts)

  def _IssueClockSyncMarker(self):
    with self._DisableGarbageCollection():
      for agent in self._active_agents_instances:
        if agent.SupportsExplicitClockSync():
          sync_id = self._GenerateClockSyncId()
          agent.RecordClockSyncMarker(sync_id,
                                      self._RecordIssuerClockSyncMarker)

  def IsChromeTracingSupported(self):
    return chrome_tracing_agent.ChromeTracingAgent.IsSupported(
        self._platform_backend)

  @property
  def is_tracing_running(self):
    return self._current_state is not None

  def _GetActiveChromeTracingAgent(self):
    if not self.is_tracing_running:
      return None
    if not self._current_state.config.enable_chrome_trace:
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

  def _IsTracingControllable(self):
    return trace_event.is_tracing_controllable()

  def ClearStateIfNeeded(self):
    chrome_tracing_agent.ClearStarupTracingStateIfNeeded(self._platform_backend)
