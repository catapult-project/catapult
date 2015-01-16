# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.timeline import trace_data as trace_data_module


class TracingControllerBackend(object):
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._current_trace_options = None
    self._current_category_filter = None
    # A map from uniquely-identifying remote port (which may be the
    # same as local port) to DevToolsClientBackend. There is no
    # guarantee that the devtools agent is still alive.
    self._devtools_clients_map = {}

  def Start(self, trace_options, category_filter, timeout):
    if self.is_tracing_running:
      return False

    assert isinstance(category_filter,
                      tracing_category_filter.TracingCategoryFilter)
    assert isinstance(trace_options,
                      tracing_options.TracingOptions)

    self._current_trace_options = trace_options
    self._current_category_filter = category_filter

    if trace_options.enable_chrome_trace:
      self._RemoveStaleDevToolsClient()
      for _, devtools_client in self._devtools_clients_map.iteritems():
        devtools_client.StartChromeTracing(
            trace_options, category_filter.filter_string, timeout)

    if trace_options.enable_platform_display_trace:
      self._platform_backend.StartDisplayTracing()

  def _RemoveStaleDevToolsClient(self):
    """Removes DevTools clients that are no longer connectable."""
    self._devtools_clients_map = {
        port: client
        for port, client in self._devtools_clients_map.iteritems()
        if client.IsAlive()
        }

  def Stop(self):
    assert self.is_tracing_running, 'Can only stop tracing when tracing.'

    trace_data_builder = trace_data_module.TraceDataBuilder()
    if self._current_trace_options.enable_chrome_trace:
      for _, devtools_client in self._devtools_clients_map.iteritems():
        # We do not check for stale DevTools client, so that we get an
        # exception if there is a stale client. This is because we
        # will potentially lose data if there is a stale client.
        devtools_client.StopChromeTracing(trace_data_builder)

    if self._current_trace_options.enable_platform_display_trace:
      surface_flinger_trace_data = self._platform_backend.StopDisplayTracing()
      trace_data_builder.AddEventsTo(
          trace_data_module.SURFACE_FLINGER_PART, surface_flinger_trace_data)

    self._current_trace_options = None
    self._current_category_filter = None
    return trace_data_builder.AsData()

  def RegisterDevToolsClient(self, devtools_client_backend):
    assert not self.is_tracing_running, (
        'Cannot add new DevTools client when tracing is running.')
    remote_port = str(devtools_client_backend.remote_port)
    self._devtools_clients_map[remote_port] = devtools_client_backend

  def IsChromeTracingSupported(self):
    self._RemoveStaleDevToolsClient()
    for _, devtools_client in self._devtools_clients_map.iteritems():
      if devtools_client.IsChromeTracingSupported():
        return True
    return False

  def IsDisplayTracingSupported(self):
    return self._platform_backend.IsDisplayTracingSupported()

  @property
  def is_tracing_running(self):
    return self._current_trace_options != None
