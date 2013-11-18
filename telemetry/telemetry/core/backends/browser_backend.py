# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.core import web_contents


class ExtensionsNotSupportedException(Exception):
  pass

class BrowserBackend(object):
  """A base class for browser backends."""

  WEBPAGEREPLAY_HOST = '127.0.0.1'

  def __init__(self, is_content_shell, supports_extensions, browser_options,
               tab_list_backend):
    assert browser_options.browser_type
    self.browser_type = browser_options.browser_type
    self.is_content_shell = is_content_shell
    self._supports_extensions = supports_extensions
    self.browser_options = browser_options
    self._browser = None
    self._tab_list_backend = tab_list_backend(self)

  def AddReplayServerOptions(self, extra_wpr_args):
    pass

  def SetBrowser(self, browser):
    self._browser = browser
    self._tab_list_backend.Init()
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
  def tab_list_backend(self):
    return self._tab_list_backend

  @property
  def supports_tracing(self):
    raise NotImplementedError()

  @property
  def supports_system_info(self):
    return False

  def StartTracing(self, custom_categories=None,
                   timeout=web_contents.DEFAULT_WEB_CONTENTS_TIMEOUT):
    raise NotImplementedError()

  def StopTracing(self):
    raise NotImplementedError()

  def GetRemotePort(self, _):
    return util.GetUnreservedAvailableLocalPort()

  def Start(self):
    raise NotImplementedError()

  def CreateForwarder(self, *port_pairs):
    raise NotImplementedError()

  def IsBrowserRunning(self):
    raise NotImplementedError()

  def GetStandardOutput(self):
    raise NotImplementedError()

  def GetStackTrace(self):
    raise NotImplementedError()

  def GetSystemInfo(self):
    raise NotImplementedError()


class DoNothingForwarder(object):
  def __init__(self, *port_pairs):
    self._host_port = port_pairs[0].local_port

  @property
  def url(self):
    assert self._host_port
    return 'http://127.0.0.1:%i' % self._host_port

  def Close(self):
    self._host_port = None
