# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import web_contents
from telemetry.core.backends import adb_commands
from telemetry.core.backends.chrome_inspector import devtools_client_backend
from telemetry.core.backends.chrome_inspector import inspector_backend

class WebViewNotFoundException(Exception):
  pass

class AndroidProcess(object):
  """Represents a single android process."""

  def __init__(self, app_backend, pid, name):
    self._app_backend = app_backend
    self._pid = pid
    self._name = name
    self._local_port = adb_commands.AllocateTestServerPort()
    self._devtools_client = None

  @property
  def pid(self):
    return self._pid

  @property
  def name(self):
    return self._name

  @property
  def _webview_port(self):
    return 'localabstract:webview_devtools_remote_%s' % str(self.pid)

  def _UpdateDevToolsClient(self):
    if self._devtools_client is None:
      self._app_backend._android_platform_backend.ForwardHostToDevice(
          self._local_port, self._webview_port)
      candidate_devtools_client = devtools_client_backend.DevToolsClientBackend(
          self._local_port, self._app_backend)
      # TODO(ariblue): Don't create a DevToolsClientBackend before confirming
      # that a devtools agent exists. This involves a minor refactor of IsAlive.
      if candidate_devtools_client.IsAlive():
        self._devtools_client = candidate_devtools_client

  def GetWebViews(self):
    webviews = []
    self._UpdateDevToolsClient()
    if self._devtools_client is not None:
      devtools_context_map = (
          self._devtools_client.GetUpdatedInspectableContexts())
      for context in devtools_context_map.contexts:
        webviews.append(web_contents.WebContents(
            devtools_context_map.GetInspectorBackend(context['id'])))
    return webviews
