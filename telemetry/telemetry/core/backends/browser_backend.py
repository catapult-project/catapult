# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.backends import app_backend
from telemetry.core import platform
from telemetry.core.platform import profiling_controller_backend
from telemetry.core import web_contents
from telemetry import decorators


class ExtensionsNotSupportedException(Exception):
  pass


class BrowserBackend(app_backend.AppBackend):
  """A base class for browser backends."""

  def __init__(self, platform_backend, supports_extensions, browser_options,
               tab_list_backend):
    assert browser_options.browser_type
    super(BrowserBackend, self).__init__(
        browser_options.browser_type, platform_backend)
    self._supports_extensions = supports_extensions
    self.browser_options = browser_options
    self._tab_list_backend_class = tab_list_backend
    self._profiling_controller_backend = (
        profiling_controller_backend.ProfilingControllerBackend(
          platform_backend, self))

  def SetBrowser(self, browser):
    super(BrowserBackend, self).SetApp(app=browser)
    if self.browser_options.netsim:
      host_platform = platform.GetHostPlatform()
      if not host_platform.CanLaunchApplication('ipfw'):
        host_platform.InstallApplication('ipfw')

  @property
  def browser(self):
    return self.app

  @property
  def profiling_controller_backend(self):
    return self._profiling_controller_backend

  @property
  def browser_type(self):
    return self.app_type

  @property
  def supports_extensions(self):
    """True if this browser backend supports extensions."""
    return self._supports_extensions

  @property
  def wpr_mode(self):
    return self.browser_options.wpr_mode

  @property
  def should_ignore_certificate_errors(self):
    return True

  @property
  def supports_tab_control(self):
    raise NotImplementedError()

  @property
  @decorators.Cache
  def tab_list_backend(self):
    return self._tab_list_backend_class(self)

  @property
  def supports_tracing(self):
    raise NotImplementedError()

  @property
  def supports_system_info(self):
    return False

  def StartTracing(self, trace_options, custom_categories=None,
                   timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    raise NotImplementedError()

  def StopTracing(self, trace_data_builder):
    raise NotImplementedError()

  def Start(self):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()

  def IsAppRunning(self):
    return self.IsBrowserRunning()

  def GetStandardOutput(self):
    raise NotImplementedError()

  def GetStackTrace(self):
    raise NotImplementedError()

  def GetSystemInfo(self):
    raise NotImplementedError()
