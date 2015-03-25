# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pipes
import sys
import time

from telemetry.core.backends import adb_commands
from telemetry.core.backends import android_command_line_backend
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import chrome_browser_backend
from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core.platform import android_platform_backend as \
  android_platform_backend_module
from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_errors  # pylint: disable=F0401
from pylib.device import intent  # pylint: disable=F0401


class AndroidBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a browser instance running on Android."""
  def __init__(self, android_platform_backend, browser_options,
               backend_settings, output_profile_path, extensions_to_load,
               target_arch):
    assert isinstance(android_platform_backend,
                      android_platform_backend_module.AndroidPlatformBackend)
    super(AndroidBrowserBackend, self).__init__(
        android_platform_backend,
        supports_tab_control=backend_settings.supports_tab_control,
        supports_extensions=False, browser_options=browser_options,
        output_profile_path=output_profile_path,
        extensions_to_load=extensions_to_load)
    if len(extensions_to_load) > 0:
      raise browser_backend.ExtensionsNotSupportedException(
          'Android browser does not support extensions.')

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._backend_settings = backend_settings
    self._target_arch = target_arch
    self._saved_sslflag = ''

    # TODO(tonyg): This is flaky because it doesn't reserve the port that it
    # allocates. Need to fix this.
    self._port = adb_commands.AllocateTestServerPort()

    # TODO(wuhu): Move to network controller backend.
    self.platform_backend.InstallTestCa()

    # Kill old browser.
    self._KillBrowser()

    if self._adb.device().old_interface.CanAccessProtectedFileContents():
      if self.browser_options.profile_dir:
        self.platform_backend.PushProfile(
            self._backend_settings.package,
            self.browser_options.profile_dir)
      elif not self.browser_options.dont_override_profile:
        self.platform_backend.RemoveProfile(
            self._backend_settings.package,
            self._backend_settings.profile_ignore_list)

    if self.browser_options.netsim:
      assert self.platform_backend.use_rndis_forwarder, (
          'Netsim requires RNDIS forwarding.')
      self.wpr_port_pairs = forwarders.PortPairs(
          http=forwarders.PortPair(0, 80),
          https=forwarders.PortPair(0, 443),
          dns=forwarders.PortPair(0, 53))

    # Set the debug app if needed.
    self.platform_backend.SetDebugApp(self._backend_settings.package)

  @property
  def _adb(self):
    return self.platform_backend.adb

  def _KillBrowser(self):
    self.platform_backend.KillApplication(self._backend_settings.package)

  def Start(self):
    self._adb.device().RunShellCommand('logcat -c')
    if self.browser_options.startup_url:
      url = self.browser_options.startup_url
    elif self.browser_options.profile_dir:
      url = None
    else:
      # If we have no existing tabs start with a blank page since default
      # startup with the NTP can lead to race conditions with Telemetry
      url = 'about:blank'

    self.platform_backend.DismissCrashDialogIfNeeded()

    browser_startup_args = self.GetBrowserStartupArgs()
    with android_command_line_backend.SetUpCommandLineFlags(
        self._adb, self._backend_settings, browser_startup_args):
      self._adb.device().StartActivity(
          intent.Intent(package=self._backend_settings.package,
                        activity=self._backend_settings.activity,
                        action=None, data=url, category=None),
          blocking=True)

      remote_devtools_port = self._backend_settings.GetDevtoolsRemotePort(
          self._adb)
      self.platform_backend.ForwardHostToDevice(self._port,
                                                remote_devtools_port)
      try:
        self._WaitForBrowserToComeUp()
        self._InitDevtoolsClientBackend(remote_devtools_port)
      except exceptions.BrowserGoneException:
        logging.critical('Failed to connect to browser.')
        device = self._adb.device()
        if not device.old_interface.CanAccessProtectedFileContents():
          logging.critical(
            'Resolve this by either: '
            '(1) Flashing to a userdebug build OR '
            '(2) Manually enabling web debugging in Chrome at '
            'Settings > Developer tools > Enable USB Web debugging.')
        sys.exit(1)
      except:
        import traceback
        traceback.print_exc()
        self.Close()
        raise

  def GetBrowserStartupArgs(self):
    args = super(AndroidBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--enable-remote-debugging')
    args.append('--disable-fre')
    args.append('--disable-external-intent-requests')
    return args

  @property
  def adb(self):
    return self._adb

  @property
  def pid(self):
    pids = self._adb.ExtractPid(self._backend_settings.package)
    if not pids:
      raise exceptions.BrowserGoneException(self.browser)
    return int(pids[0])

  @property
  def browser_directory(self):
    return None

  @property
  def profile_directory(self):
    return self._backend_settings.profile_dir

  @property
  def package(self):
    return self._backend_settings.package

  @property
  def activity(self):
    return self._backend_settings.activity

  def __del__(self):
    self.Close()

  def Close(self):
    super(AndroidBrowserBackend, self).Close()

    self.platform_backend.RemoveTestCa()

    self._KillBrowser()

    if self._output_profile_path:
      self.platform_backend.PullProfile(
          self._backend_settings.package, self._output_profile_path)

  def IsBrowserRunning(self):
    return self.platform_backend.IsAppRunning(self._backend_settings.package)

  def GetStandardOutput(self):
    return self.platform_backend.GetStandardOutput()

  def GetStackTrace(self):
    return self.platform_backend.GetStackTrace(self._target_arch)

  @property
  def should_ignore_certificate_errors(self):
    return not self.platform_backend.is_test_ca_installed
