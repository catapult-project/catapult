# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import sys

from telemetry.core.backends.chrome_inspector import devtools_http
from telemetry.core.backends.chrome_inspector import inspector_backend
from telemetry.core.backends.chrome_inspector import tracing_backend
from telemetry.core import exceptions
from telemetry.core.platform.tracing_agent import chrome_tracing_agent
from telemetry import decorators
from telemetry.timeline import trace_data as trace_data_module


class TabNotFoundError(exceptions.Error):
  pass


def IsDevToolsAgentAvailable(port):
  """Returns True if a DevTools agent is available on the given port."""
  devtools_http_instance = devtools_http.DevToolsHttp(port)
  try:
    return _IsDevToolsAgentAvailable(devtools_http.DevToolsHttp(port))
  finally:
    devtools_http_instance.Disconnect()


# TODO(nednguyen): Find a more reliable way to check whether the devtool agent
# is still alive.
def _IsDevToolsAgentAvailable(devtools_http_instance):
  try:
    devtools_http_instance.Request('')
  except devtools_http.DevToolsClientConnectionError:
    return False
  else:
    return True


class DevToolsClientBackend(object):
  """An object that communicates with Chrome's devtools.

  This class owns a map of InspectorBackends. It is responsible for creating
  them and destroying them.
  """
  def __init__(self, devtools_port, remote_devtools_port, app_backend):
    """Creates a new DevToolsClientBackend.

    A DevTools agent must exist on the given devtools_port.

    Args:
      devtools_port: The port to use to connect to DevTools agent.
      remote_devtools_port: In some cases (e.g., app running on
          Android device, devtools_port is the forwarded port on the
          host platform. We also need to know the remote_devtools_port
          so that we can uniquely identify the DevTools agent.
      app_backend: For the app that contains the DevTools agent.
    """
    self._devtools_port = devtools_port
    self._remote_devtools_port = remote_devtools_port
    self._devtools_http = devtools_http.DevToolsHttp(devtools_port)
    self._tracing_backend = None
    self._app_backend = app_backend
    self._devtools_context_map_backend = _DevToolsContextMapBackend(
        self._app_backend, self)

    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
      self, self._app_backend.platform_backend)

  @property
  def remote_port(self):
    return self._remote_devtools_port

  def IsAlive(self):
    """Whether the DevTools server is available and connectable."""
    return _IsDevToolsAgentAvailable(self._devtools_http)

  def Close(self):
    if self._tracing_backend:
      self._tracing_backend.Close()
      self._tracing_backend = None

  @decorators.Cache
  def GetChromeBranchNumber(self):
    # Detect version information.
    resp = self._devtools_http.RequestJson('version')
    if 'Protocol-Version' in resp:
      if 'Browser' in resp:
        branch_number_match = re.search(r'Chrome/\d+\.\d+\.(\d+)\.\d+',
                                        resp['Browser'])
      else:
        branch_number_match = re.search(
            r'Chrome/\d+\.\d+\.(\d+)\.\d+ (Mobile )?Safari',
            resp['User-Agent'])

      if branch_number_match:
        branch_number = int(branch_number_match.group(1))
        if branch_number:
          return branch_number

    # Branch number can't be determined, so fail any branch number checks.
    return 0

  def _ListInspectableContexts(self):
    return self._devtools_http.RequestJson('')

  def CreateNewTab(self, timeout):
    """Creates a new tab.

    Raises:
      devtools_http.DevToolsClientConnectionError
    """
    self._devtools_http.Request('new', timeout=timeout)

  def CloseTab(self, tab_id, timeout):
    """Closes the tab with the given id.

    Raises:
      devtools_http.DevToolsClientConnectionError
      TabNotFoundError
    """
    try:
      return self._devtools_http.Request('close/%s' % tab_id,
                                         timeout=timeout)
    except devtools_http.DevToolsClientUrlError:
      error = TabNotFoundError(
          'Unable to close tab, tab id not found: %s' % tab_id)
      raise error, None, sys.exc_info()[2]

  def ActivateTab(self, tab_id, timeout):
    """Activates the tab with the given id.

    Raises:
      devtools_http.DevToolsClientConnectionError
      TabNotFoundError
    """
    try:
      return self._devtools_http.Request('activate/%s' % tab_id,
                                         timeout=timeout)
    except devtools_http.DevToolsClientUrlError:
      error = TabNotFoundError(
          'Unable to activate tab, tab id not found: %s' % tab_id)
      raise error, None, sys.exc_info()[2]

  def GetUrl(self, tab_id):
    """Returns the URL of the tab with |tab_id|, as reported by devtools.

    Raises:
      devtools_http.DevToolsClientConnectionError
    """
    for c in self._ListInspectableContexts():
      if c['id'] == tab_id:
        return c['url']
    return None

  def IsInspectable(self, tab_id):
    """Whether the tab with |tab_id| is inspectable, as reported by devtools.

    Raises:
      devtools_http.DevToolsClientConnectionError
    """
    contexts  = self._ListInspectableContexts()
    return tab_id in [c['id'] for c in contexts]

  def GetUpdatedInspectableContexts(self):
    """Returns an updated instance of _DevToolsContextMapBackend."""
    contexts = self._ListInspectableContexts()
    self._devtools_context_map_backend._Update(contexts)
    return self._devtools_context_map_backend

  def _CreateTracingBackendIfNeeded(self):
    if not self._tracing_backend:
      self._tracing_backend = tracing_backend.TracingBackend(
          self._devtools_port)

  def IsChromeTracingSupported(self):
    self._CreateTracingBackendIfNeeded()
    return self._tracing_backend.IsTracingSupported()

  def StartChromeTracing(
      self, trace_options, custom_categories=None, timeout=10):
    """
    Args:
        trace_options: An tracing_options.TracingOptions instance.
        custom_categories: An optional string containing a list of
                         comma separated categories that will be traced
                         instead of the default category set.  Example: use
                         "webkit,cc,disabled-by-default-cc.debug" to trace only
                         those three event categories.
    """
    assert trace_options and trace_options.enable_chrome_trace
    self._CreateTracingBackendIfNeeded()
    return self._tracing_backend.StartTracing(
        trace_options, custom_categories, timeout)

  def StopChromeTracing(self, trace_data_builder, timeout=30):
    context_map = self.GetUpdatedInspectableContexts()
    for context in context_map.contexts:
      if context['type'] not in ['iframe', 'page', 'webview']:
        continue
      context_id = context['id']
      backend = context_map.GetInspectorBackend(context_id)
      success = backend.EvaluateJavaScript(
          "console.time('" + backend.id + "');" +
          "console.timeEnd('" + backend.id + "');" +
          "console.time.toString().indexOf('[native code]') != -1;")
      if not success:
        raise Exception('Page stomped on console.time')
      trace_data_builder.AddEventsTo(
          trace_data_module.TAB_ID_PART, [backend.id])

    assert self._tracing_backend
    return self._tracing_backend.StopTracing(trace_data_builder, timeout)


class _DevToolsContextMapBackend(object):
  def __init__(self, app_backend, devtools_client):
    self._app_backend = app_backend
    self._devtools_client = devtools_client
    self._contexts = None
    self._inspector_backends_dict = {}

  @property
  def contexts(self):
    """The most up to date contexts data.

    Returned in the order returned by devtools agent."""
    return self._contexts

  def GetContextInfo(self, context_id):
    for context in self._contexts:
      if context['id'] == context_id:
        return context
    raise KeyError('Cannot find a context with id=%s' % context_id)

  def GetInspectorBackend(self, context_id):
    """Gets an InspectorBackend instance for the given context_id.

    This lazily creates InspectorBackend for the context_id if it does
    not exist yet. Otherwise, it will return the cached instance."""
    if context_id in self._inspector_backends_dict:
      return self._inspector_backends_dict[context_id]

    for context in self._contexts:
      if context['id'] == context_id:
        new_backend = inspector_backend.InspectorBackend(
            self._app_backend.app, self._devtools_client, context)
        self._inspector_backends_dict[context_id] = new_backend
        return new_backend

    raise KeyError('Cannot find a context with id=%s' % context_id)

  def _Update(self, contexts):
    # Remove InspectorBackend that is not in the current inspectable
    # contexts list.
    context_ids = [context['id'] for context in contexts]
    for context_id in self._inspector_backends_dict.keys():
      if context_id not in context_ids:
        backend = self._inspector_backends_dict[context_id]
        backend.Disconnect()
        del self._inspector_backends_dict[context_id]

    valid_contexts = []
    for context in contexts:
      # If the context does not have webSocketDebuggerUrl, skip it.
      # If an InspectorBackend is already created for the tab,
      # webSocketDebuggerUrl will be missing, and this is expected.
      context_id = context['id']
      if context_id not in self._inspector_backends_dict:
        if 'webSocketDebuggerUrl' not in context:
          logging.debug('webSocketDebuggerUrl missing, removing %s'
                        % context_id)
          continue
      valid_contexts.append(context)
    self._contexts = valid_contexts
