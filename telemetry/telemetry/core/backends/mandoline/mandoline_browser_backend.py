# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import tab_list_backend
from telemetry.core.backends.chrome_inspector import devtools_client_backend
from telemetry.core import exceptions
from telemetry.core import util
from telemetry.core import wpr_modes


class MandolineBrowserBackend(browser_backend.BrowserBackend):
  """An abstract class for mandoline browser backends. Provides basic
  functionality once a remote-debugger port has been established."""
  # It is OK to have abstract methods. pylint: disable=W0223

  def __init__(self, platform_backend, browser_options):
    super(MandolineBrowserBackend, self).__init__(
        platform_backend=platform_backend,
        supports_extensions=False,
        browser_options=browser_options,
        tab_list_backend=tab_list_backend.TabListBackend)
    self._port = None
    self._devtools_client = None

    # Some of the browser options are not supported by mandoline yet.
    self._CheckUnsupportedBrowserOptions(browser_options)

  @property
  def devtools_client(self):
    return self._devtools_client

  def GetBrowserStartupArgs(self):
    args = []
    args.extend(self.browser_options.extra_browser_args)
    return args

  def HasBrowserFinishedLaunching(self):
    assert self._port, 'No DevTools port info available.'
    return devtools_client_backend.IsDevToolsAgentAvailable(self._port)

  def _InitDevtoolsClientBackend(self, remote_devtools_port=None):
    """ Initiates the devtool client backend which allows browser connection
    through browser' devtool.

    Args:
      remote_devtools_port: The remote devtools port, if any. Otherwise assumed
          to be the same as self._port.
    """
    assert not self._devtools_client, (
        'Devtool client backend cannot be init twice')
    self._devtools_client = devtools_client_backend.DevToolsClientBackend(
        self._port, remote_devtools_port or self._port, self)

  def _WaitForBrowserToComeUp(self):
    """ Waits for browser to come up. """
    try:
      timeout = self.browser_options.browser_startup_timeout
      util.WaitFor(self.HasBrowserFinishedLaunching, timeout=timeout)
    except (exceptions.TimeoutException, exceptions.ProcessGoneException) as e:
      if not self.IsBrowserRunning():
        raise exceptions.BrowserGoneException(self.browser, e)
      raise exceptions.BrowserConnectionGoneException(self.browser, e)

  @property
  def browser_directory(self):
    raise NotImplementedError()

  @property
  def profile_directory(self):
    raise NotImplementedError()

  @property
  def supports_tab_control(self):
    return False

  @property
  def supports_tracing(self):
    return False

  @property
  def supports_system_info(self):
    return False

  def GetProcessName(self, cmd_line):
    """Returns a user-friendly name for the process of the given |cmd_line|."""
    if not cmd_line:
      return 'unknown'
    m = re.search(r'\s--child-process(\s.*)?$', cmd_line)
    if not m:
      return 'browser'
    return 'child-process'

  def Close(self):
    if self._devtools_client:
      self._devtools_client.Close()
      self._devtools_client = None

  def _CheckUnsupportedBrowserOptions(self, browser_options):
    def _RaiseForUnsupportedOption(name):
      raise Exception('BrowserOptions.%s is ignored. Value: %r'
                          % (name, getattr(browser_options, name)))

    if browser_options.dont_override_profile:
      _RaiseForUnsupportedOption('dont_override_profile')

    if browser_options.profile_dir:
      _RaiseForUnsupportedOption('profile_dir')

    if browser_options.profile_type and browser_options.profile_type != 'clean':
      _RaiseForUnsupportedOption('profile_type')

    if browser_options.extra_wpr_args:
      _RaiseForUnsupportedOption('extra_wpr_args')

    if browser_options.wpr_mode != wpr_modes.WPR_OFF:
      _RaiseForUnsupportedOption('wpr_mode')

    if browser_options.netsim:
      _RaiseForUnsupportedOption('netsim')

    if not browser_options.disable_background_networking:
      _RaiseForUnsupportedOption('disable_background_networking')

    if browser_options.no_proxy_server:
      _RaiseForUnsupportedOption('no_proxy_server')

    if browser_options.browser_user_agent_type:
      _RaiseForUnsupportedOption('browser_user_agent_type')

    if browser_options.use_devtools_active_port:
      _RaiseForUnsupportedOption('use_devtools_active_port')
