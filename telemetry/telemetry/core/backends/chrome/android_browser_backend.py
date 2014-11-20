# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import pipes
import sys
import time

from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import util
from telemetry.core.backends import adb_commands
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import chrome_browser_backend
from telemetry.core.platform import android_platform_backend as \
  android_platform_backend_module
from telemetry.core.forwarders import android_forwarder

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_errors  # pylint: disable=F0401
from pylib.device import intent  # pylint: disable=F0401


class AndroidBrowserBackendSettings(object):

  def __init__(self, activity, cmdline_file, package, pseudo_exec_name,
               supports_tab_control):
    self.activity = activity
    self._cmdline_file = cmdline_file
    self.package = package
    self.pseudo_exec_name = pseudo_exec_name
    self.supports_tab_control = supports_tab_control

  def GetCommandLineFile(self, is_user_debug_build):  # pylint: disable=W0613
    return self._cmdline_file

  def GetDevtoolsRemotePort(self, adb):
    raise NotImplementedError()

  @property
  def profile_ignore_list(self):
    # Don't delete lib, since it is created by the installer.
    return ['lib']


class ChromeBackendSettings(AndroidBrowserBackendSettings):
  # Stores a default Preferences file, re-used to speed up "--page-repeat".
  _default_preferences_file = None

  def GetCommandLineFile(self, is_user_debug_build):
    if is_user_debug_build:
      return '/data/local/tmp/chrome-command-line'
    else:
      return '/data/local/chrome-command-line'

  def __init__(self, package):
    super(ChromeBackendSettings, self).__init__(
        activity='com.google.android.apps.chrome.Main',
        cmdline_file=None,
        package=package,
        pseudo_exec_name='chrome',
        supports_tab_control=True)

  def GetDevtoolsRemotePort(self, adb):
    return 'localabstract:chrome_devtools_remote'


class ContentShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, package):
    super(ContentShellBackendSettings, self).__init__(
        activity='org.chromium.content_shell_apk.ContentShellActivity',
        cmdline_file='/data/local/tmp/content-shell-command-line',
        package=package,
        pseudo_exec_name='content_shell',
        supports_tab_control=False)

  def GetDevtoolsRemotePort(self, adb):
    return 'localabstract:content_shell_devtools_remote'


class ChromeShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, package):
    super(ChromeShellBackendSettings, self).__init__(
          activity='org.chromium.chrome.shell.ChromeShellActivity',
          cmdline_file='/data/local/tmp/chrome-shell-command-line',
          package=package,
          pseudo_exec_name='chrome_shell',
          supports_tab_control=False)

  def GetDevtoolsRemotePort(self, adb):
    return 'localabstract:chrome_shell_devtools_remote'


class WebviewBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, package,
               activity='org.chromium.telemetry_shell.TelemetryActivity',
               cmdline_file='/data/local/tmp/webview-command-line'):
    super(WebviewBackendSettings, self).__init__(
        activity=activity,
        cmdline_file=cmdline_file,
        package=package,
        pseudo_exec_name='webview',
        supports_tab_control=False)

  def GetDevtoolsRemotePort(self, adb):
    # The DevTools socket name for WebView depends on the activity PID's.
    retries = 0
    timeout = 1
    pid = None
    while True:
      pids = adb.ExtractPid(self.package)
      if len(pids) > 0:
        pid = pids[-1]
        break
      time.sleep(timeout)
      retries += 1
      timeout *= 2
      if retries == 4:
        logging.critical('android_browser_backend: Timeout while waiting for '
                         'activity %s:%s to come up',
                         self.package,
                         self.activity)
        raise exceptions.BrowserGoneException(self.browser,
                                              'Timeout waiting for PID.')
    return 'localabstract:webview_devtools_remote_%s' % str(pid)


class WebviewShellBackendSettings(WebviewBackendSettings):
  def __init__(self, package):
    super(WebviewShellBackendSettings, self).__init__(
        activity='org.chromium.android_webview.shell.AwShellActivity',
        cmdline_file='/data/local/tmp/android-webview-command-line',
        package=package)


class AndroidBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a browser instance running on Android."""
  def __init__(self, android_platform_backend, browser_options,
               backend_settings, use_rndis_forwarder, output_profile_path,
               extensions_to_load, target_arch):
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
    self._saved_cmdline = ''
    self._target_arch = target_arch
    self._saved_sslflag = ''

    # TODO(tonyg): This is flaky because it doesn't reserve the port that it
    # allocates. Need to fix this.
    self._port = adb_commands.AllocateTestServerPort()

    # TODO(wuhu): Move to network controller backend.
    self._platform_backend.InstallTestCa()

    # Kill old browser.
    self._KillBrowser()

    if self._adb.device().old_interface.CanAccessProtectedFileContents():
      if self.browser_options.profile_dir:
        self._platform_backend.PushProfile(
            self._backend_settings.package,
            self.browser_options.profile_dir)
      elif not self.browser_options.dont_override_profile:
        self._platform_backend.RemoveProfile(
            self._backend_settings.package,
            self._backend_settings.profile_ignore_list)

    self._forwarder_factory = android_forwarder.AndroidForwarderFactory(
        self._adb, use_rndis_forwarder)

    if self.browser_options.netsim or use_rndis_forwarder:
      assert use_rndis_forwarder, 'Netsim requires RNDIS forwarding.'
      self.wpr_port_pairs = forwarders.PortPairs(
          http=forwarders.PortPair(0, 80),
          https=forwarders.PortPair(0, 443),
          dns=forwarders.PortPair(0, 53))

    # Set the debug app if needed.
    self._platform_backend.SetDebugApp(self._backend_settings.package)

  @property
  def _adb(self):
    return self._platform_backend.adb

  def _KillBrowser(self):
    self._platform_backend.KillApplication(self._backend_settings.package)

  def _SetUpCommandLine(self):
    def QuoteIfNeeded(arg):
      # Properly escape "key=valueA valueB" to "key='valueA valueB'"
      # Values without spaces, or that seem to be quoted are left untouched.
      # This is required so CommandLine.java can parse valueB correctly rather
      # than as a separate switch.
      params = arg.split('=', 1)
      if len(params) != 2:
        return arg
      key, values = params
      if ' ' not in values:
        return arg
      if values[0] in '"\'' and values[-1] == values[0]:
        return arg
      return '%s=%s' % (key, pipes.quote(values))
    args = [self._backend_settings.pseudo_exec_name]
    args.extend(self.GetBrowserStartupArgs())
    content = ' '.join(QuoteIfNeeded(arg) for arg in args)
    cmdline_file = self._backend_settings.GetCommandLineFile(
        self._adb.IsUserBuild())

    try:
      # Save the current command line to restore later, except if it appears to
      # be a  Telemetry created one. This is to prevent a common bug where
      # --host-resolver-rules borks people's browsers if something goes wrong
      # with Telemetry.
      self._saved_cmdline = ''.join(self._adb.device().ReadFile(cmdline_file))
      if '--host-resolver-rules' in self._saved_cmdline:
        self._saved_cmdline = ''
      self._adb.device().WriteFile(cmdline_file, content, as_root=True)
    except device_errors.CommandFailedError:
      logging.critical('Cannot set Chrome command line. '
                       'Fix this by flashing to a userdebug build.')
      sys.exit(1)

  def _RestoreCommandLine(self):
    cmdline_file = self._backend_settings.GetCommandLineFile(
        self._adb.IsUserBuild())
    self._adb.device().WriteFile(cmdline_file, self._saved_cmdline,
                                 as_root=True)

  def Start(self):
    self._SetUpCommandLine()

    self._adb.device().RunShellCommand('logcat -c')
    if self.browser_options.startup_url:
      url = self.browser_options.startup_url
    elif self.browser_options.profile_dir:
      url = None
    else:
      # If we have no existing tabs start with a blank page since default
      # startup with the NTP can lead to race conditions with Telemetry
      url = 'about:blank'

    self._platform_backend.DismissCrashDialogIfNeeded()

    self._adb.device().StartActivity(
        intent.Intent(package=self._backend_settings.package,
                      activity=self._backend_settings.activity,
                      action=None, data=url, category=None),
        blocking=True)

    self._platform_backend.ForwardHostToDevice(
        self._port, self._backend_settings.GetDevtoolsRemotePort(self._adb))

    try:
      self._WaitForBrowserToComeUp()
    except exceptions.BrowserGoneException:
      logging.critical('Failed to connect to browser.')
      if not self._adb.device().old_interface.CanAccessProtectedFileContents():
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
    finally:
      self._RestoreCommandLine()

  def GetBrowserStartupArgs(self):
    args = super(AndroidBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--enable-remote-debugging')
    args.append('--disable-fre')
    args.append('--disable-external-intent-requests')
    return args

  @property
  def forwarder_factory(self):
    return self._forwarder_factory

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

    self._platform_backend.RemoveTestCa()

    self._KillBrowser()

    if self._output_profile_path:
      self._platform_backend.PullProfile(
          self._backend_settings.package, self._output_profile_path)

  def IsBrowserRunning(self):
    return self._platform_backend.IsAppRunning(self._backend_settings.package)

  def GetRemotePort(self, local_port):
    return local_port

  def GetStandardOutput(self):
    return self._platform_backend.GetStandardOutput()

  def GetStackTrace(self):
    return self._platform_backend.GetStackTrace(self._target_arch)

  @property
  def should_ignore_certificate_errors(self):
    return not self._platform_backend.is_test_ca_installed
