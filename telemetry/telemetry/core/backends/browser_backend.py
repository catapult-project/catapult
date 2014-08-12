# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import web_contents
from telemetry.core.forwarders import do_nothing_forwarder


class ExtensionsNotSupportedException(Exception):
  pass


class BrowserBackend(object):
  """A base class for browser backends."""

  def __init__(self, supports_extensions, browser_options, tab_list_backend):
    assert browser_options.browser_type
    self.browser_type = browser_options.browser_type
    self._supports_extensions = supports_extensions
    self.browser_options = browser_options
    self._browser = None
    self._tab_list_backend_class = tab_list_backend
    self._forwarder_factory = None

  def AddReplayServerOptions(self, extra_wpr_args):
    pass

  def SetBrowser(self, browser):
    self._browser = browser
    if (self.browser_options.netsim and
        not browser.platform.CanLaunchApplication('ipfw')):
      browser.platform.InstallApplication('ipfw')

  @property
  def browser(self):
    return self._browser

  @property
  def supports_extensions(self):
    """True if this browser backend supports extensions."""
    return self._supports_extensions

  @property
  def wpr_mode(self):
    return self.browser_options.wpr_mode

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

  @property
  def forwarder_factory(self):
    if not self._forwarder_factory:
      self._forwarder_factory = do_nothing_forwarder.DoNothingForwarderFactory()
    return self._forwarder_factory

  def StartTracing(self, trace_options, custom_categories=None,
                   timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    raise NotImplementedError()

  @property
  def is_tracing_running(self):
    return False

  def StopTracing(self):
    raise NotImplementedError()

  def GetRemotePort(self, port):
    return port

  def Start(self):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()

  def GetStandardOutput(self):
    raise NotImplementedError()

  def GetStackTrace(self):
    raise NotImplementedError()

  def GetSystemInfo(self):
    raise NotImplementedError()
