# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys
import traceback

from telemetry.core.platform import tracing_agent


class ChromeTracingStartedError(Exception):
  pass


class ChromeTracingStoppedError(Exception):
  pass


class ChromeTracingAgent(tracing_agent.TracingAgent):
  # A singleton map from platform backends to maps of uniquely-identifying
  # remote port (which may be the same as local port) to DevToolsClientBackend.
  # There is no guarantee that the devtools agent is still alive.
  _platform_backends_to_devtools_clients_maps = {}
  _is_tracing_running_for_platform_backend = {}
  _is_tracing_running_for_platform_backend.setdefault(False)

  def __init__(self, platform_backend):
    super(ChromeTracingAgent, self).__init__(platform_backend)

  @classmethod
  def _RemoveStaleDevToolsClient(cls, platform_backend):
    """Removes DevTools clients that are no longer connectable."""
    devtools_clients_map = cls._platform_backends_to_devtools_clients_maps.get(
        platform_backend, {})
    devtools_clients_map = {
        port: client
        for port, client in devtools_clients_map.iteritems()
        if client.IsAlive()
        }
    cls._platform_backends_to_devtools_clients_maps[platform_backend] = (
        devtools_clients_map)

  @classmethod
  def RegisterDevToolsClient(cls, devtools_client_backend, platform_backend):
    is_tracing_running = cls._is_tracing_running_for_platform_backend.get(
        platform_backend)
    if is_tracing_running:
      raise ChromeTracingStartedError(
          'Cannot add new DevTools client when tracing is running on '
          'platform backend %s.' % platform_backend)
    remote_port = str(devtools_client_backend.remote_port)
    if platform_backend not in cls._platform_backends_to_devtools_clients_maps:
      cls._platform_backends_to_devtools_clients_maps[platform_backend] = {}
    devtools_clients_map = (
      cls._platform_backends_to_devtools_clients_maps[platform_backend])
    devtools_clients_map[remote_port] = devtools_client_backend

  @classmethod
  def IsSupported(cls, platform_backend):
    cls._RemoveStaleDevToolsClient(platform_backend)
    devtools_clients_map = cls._platform_backends_to_devtools_clients_maps.get(
        platform_backend, {})
    for _, devtools_client in devtools_clients_map.iteritems():
      if devtools_client.IsChromeTracingSupported():
        return True
    return False

  @property
  def _is_active(self):
    return self._is_tracing_running_for_platform_backend.get(
        self._platform_backend)

  @_is_active.setter
  def _is_active(self, value):
    self._is_tracing_running_for_platform_backend[self._platform_backend] = (
        value)

  def Start(self, trace_options, category_filter, timeout):
    if not trace_options.enable_chrome_trace:
      return False

    if self._is_active:
      raise ChromeTracingStartedError(
          'Tracing is already running on platform backend %s.'
          % self._platform_backend)
    self._RemoveStaleDevToolsClient(self._platform_backend)
    devtools_clients_map = self._platform_backends_to_devtools_clients_maps.get(
        self._platform_backend, {})
    if not devtools_clients_map:
      return False
    for _, devtools_client in devtools_clients_map.iteritems():
      devtools_client.StartChromeTracing(
          trace_options, category_filter.filter_string, timeout)
    self._is_active = True
    return True

  def Stop(self, trace_data_builder):
    devtools_clients_map = (
      self._platform_backends_to_devtools_clients_maps[self._platform_backend])
    raised_execption_messages = []
    for devtools_port, devtools_client in devtools_clients_map.iteritems():
      # We do not check for stale DevTools client, so that we get an
      # exception if there is a stale client. This is because we
      # will potentially lose data if there is a stale client.
      try:
        devtools_client.StopChromeTracing(trace_data_builder)
      except Exception:
        raised_execption_messages.append(
          'Error when trying to stop tracing on devtools at port %s:\n%s'
          % (devtools_port,
             ''.join(traceback.format_exception(*sys.exc_info()))))

    self._is_active = False
    if raised_execption_messages:
      raise ChromeTracingStoppedError(
          'Exceptions raised when trying to stop devtool tracing\n:' +
          '\n'.join(raised_execption_messages))
