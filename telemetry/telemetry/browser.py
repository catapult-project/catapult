# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import temporary_http_server
from telemetry import browser_credentials
from telemetry import wpr_modes
from telemetry import wpr_server


class Browser(object):
  """A running browser instance that can be controlled in a limited way.

  To create a browser instance, use browser_finder.FindBrowser.

  Be sure to clean up after yourself by calling Close() when you are done with
  the browser. Or better yet:
    browser_to_create = FindBrowser(options)
    with browser_to_create.Create() as browser:
      ... do all your operations on browser here
  """
  def __init__(self, backend, platform):
    self._backend = backend
    self._http_server = None
    self._wpr_server = None
    self._platform = platform
    self.credentials = browser_credentials.BrowserCredentials()

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()

  @property
  def platform(self):
    return self._platform

  @property
  def browser_type(self):
    return self._backend.browser_type

  @property
  def is_content_shell(self):
    """Returns whether this browser is a content shell, only."""
    return self._backend.is_content_shell

  @property
  def supports_tab_control(self):
    return self._backend.supports_tab_control

  @property
  def tabs(self):
    return self._backend.tabs

  @property
  def supports_tracing(self):
    return self._backend.supports_tracing

  def StartTracing(self):
    return self._backend.StartTracing()

  def StopTracing(self):
    return self._backend.StopTracing()

  def GetTrace(self):
    return self._backend.GetTrace()

  def Close(self):
    """Closes this browser."""
    if self._wpr_server:
      self._wpr_server.Close()
      self._wpr_server = None

    if self._http_server:
      self._http_server.Close()
      self._http_server = None

    self._backend.Close()
    self.credentials = None

  @property
  def http_server(self):
    return self._http_server

  def SetHTTPServerDirectory(self, path):
    if path:
      abs_path = os.path.abspath(path)
      if self._http_server and self._http_server.path == path:
        return
    else:
      abs_path = None

    if self._http_server:
      self._http_server.Close()
      self._http_server = None

    if not abs_path:
      return

    self._http_server = temporary_http_server.TemporaryHTTPServer(
      self._backend, abs_path)

  def SetReplayArchivePath(self, archive_path):
    if self._wpr_server:
      self._wpr_server.Close()
      self._wpr_server = None

    if not archive_path:
      return None

    if self._backend.wpr_mode == wpr_modes.WPR_OFF:
      return

    use_record_mode = self._backend.wpr_mode == wpr_modes.WPR_RECORD
    if not use_record_mode:
      assert os.path.isfile(archive_path)

    self._wpr_server = wpr_server.ReplayServer(
        self._backend,
        archive_path,
        use_record_mode,
        self._backend.WEBPAGEREPLAY_HOST,
        self._backend.WEBPAGEREPLAY_HTTP_PORT,
        self._backend.WEBPAGEREPLAY_HTTPS_PORT)

  def GetStandardOutput(self):
    return self._backend.GetStandardOutput()
