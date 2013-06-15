# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys
import tempfile
import time

from telemetry.core import exceptions
from telemetry.core.chrome import adb_commands
from telemetry.core.chrome import browser_backend


class AndroidBrowserBackendSettings(object):
  def __init__(self, adb, activity, cmdline_file, package, pseudo_exec_name):
    self.adb = adb
    self.activity = activity
    self.cmdline_file = cmdline_file
    self.package = package
    self.pseudo_exec_name = pseudo_exec_name

  def GetDevtoolsRemotePort(self):
    raise NotImplementedError()

  def RemoveProfile(self):
    self.adb.RunShellCommand(
        'su -c rm -r "%s"' % self._profile_dir)

  def PushProfile(self, _):
    logging.critical('Profiles cannot be overriden with current configuration')
    sys.exit(1)

  @property
  def is_content_shell(self):
    return False

  @property
  def _profile_dir(self):
    raise NotImplementedError()


class ChromeBackendSettings(AndroidBrowserBackendSettings):
  # Stores a default Preferences file, re-used to speed up "--page-repeat".
  _default_preferences_file = None

  def __init__(self, adb, package):
    super(ChromeBackendSettings, self).__init__(
        adb=adb,
        activity='com.google.android.apps.chrome.Main',
        cmdline_file='/data/local/chrome-command-line',
        package=package,
        pseudo_exec_name='chrome')

  def GetDevtoolsRemotePort(self):
    return 'localabstract:chrome_devtools_remote'

  def PushProfile(self, new_profile_dir):
    self.adb.Push(new_profile_dir, self._profile_dir)

  @property
  def _profile_dir(self):
    return '/data/data/%s/app_chrome/' % self.package


class ContentShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(ContentShellBackendSettings, self).__init__(
        adb=adb,
        activity='org.chromium.content_shell_apk.ContentShellActivity',
        cmdline_file='/data/local/tmp/content-shell-command-line',
        package=package,
        pseudo_exec_name='content_shell')

  def GetDevtoolsRemotePort(self):
    return 'localabstract:content_shell_devtools_remote'

  @property
  def is_content_shell(self):
    return True

  @property
  def _profile_dir(self):
    return '/data/data/%s/app_content_shell/' % self.package


class ChromiumTestShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(ChromiumTestShellBackendSettings, self).__init__(
          adb=adb,
          activity='org.chromium.chrome.testshell.ChromiumTestShellActivity',
          cmdline_file='/data/local/tmp/chromium-testshell-command-line',
          package=package,
          pseudo_exec_name='chromium_testshell')

  def GetDevtoolsRemotePort(self):
    return 'localabstract:chromium_testshell_devtools_remote'

  @property
  def is_content_shell(self):
    return True

  @property
  def _profile_dir(self):
    return '/data/data/%s/app_chromiumtestshell/' % self.package


class WebviewBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(WebviewBackendSettings, self).__init__(
        adb=adb,
        activity='com.android.webview.chromium.shell.TelemetryActivity',
        cmdline_file='/data/local/tmp/webview-command-line',
        package=package,
        pseudo_exec_name='webview')

  def GetDevtoolsRemotePort(self):
    # The DevTools socket name for WebView depends on the activity PID's.
    retries = 0
    timeout = 1
    pid = None
    while True:
      pids = self.adb.ExtractPid(self.package)
      if (len(pids) > 0):
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
        raise exceptions.BrowserGoneException('Timeout waiting for PID.')
    return 'localabstract:webview_devtools_remote_%s' % str(pid)

  @property
  def _profile_dir(self):
    return '/data/data/%s/app_webview/' % self.package


class AndroidBrowserBackend(browser_backend.BrowserBackend):
  """The backend for controlling a browser instance running on Android.
  """
  def __init__(self, options, backend_settings):
    super(AndroidBrowserBackend, self).__init__(
        is_content_shell=backend_settings.is_content_shell,
        supports_extensions=False, options=options)
    if len(options.extensions_to_load) > 0:
      raise browser_backend.ExtensionsNotSupportedException(
          'Android browser does not support extensions.')
    # Initialize fields so that an explosion during init doesn't break in Close.
    self._options = options
    self._adb = backend_settings.adb
    self._backend_settings = backend_settings
    self._saved_cmdline = None
    if not options.keep_test_server_ports:
      adb_commands.ResetTestServerPortAllocation()
    self._port = adb_commands.AllocateTestServerPort()

    # Kill old browser.
    self._adb.CloseApplication(self._backend_settings.package)
    self._adb.KillAll('device_forwarder')

    if self._adb.Adb().CanAccessProtectedFileContents():
      if not options.dont_override_profile:
        self._backend_settings.RemoveProfile()
      if options.profile_dir:
        self._backend_settings.PushProfile(options.profile_dir)

    # Set up the command line.
    self._saved_cmdline = ''.join(self._adb.Adb().GetProtectedFileContents(
        self._backend_settings.cmdline_file) or [])
    args = [backend_settings.pseudo_exec_name]
    args.extend(self.GetBrowserStartupArgs())
    def QuoteIfNeeded(arg):
      # Escape 'key=valueA valueB' to 'key="valueA valueB"'
      # Already quoted values, or values without space are left untouched.
      # This is required so CommandLine.java can parse valueB correctly rather
      # than as a separate switch.
      params = arg.split('=')
      if len(params) != 2:
        return arg
      key, values = params
      if ' ' not in values:
        return arg
      if values[0] in '"\'' and values[-1] == values[0]:
        return arg
      return '%s="%s"' % (key, values)
    args = map(QuoteIfNeeded, args)
    self._adb.Adb().SetProtectedFileContents(
        self._backend_settings.cmdline_file, ' '.join(args))

    # Start it up with a fresh log.
    self._adb.RunShellCommand('logcat -c')
    self._adb.StartActivity(self._backend_settings.package,
                            self._backend_settings.activity,
                            True,
                            None,
                            'chrome://newtab/')

    self._adb.Forward('tcp:%d' % self._port,
                      backend_settings.GetDevtoolsRemotePort())

    try:
      self._WaitForBrowserToComeUp()
      self._PostBrowserStartupInitialization()
    except exceptions.BrowserGoneException:
      logging.critical('Failed to connect to browser.')
      if not self._adb.IsRootEnabled():
        logging.critical(
          'Ensure web debugging is enabled in Chrome at '
          '"Settings > Developer tools > Enable USB Web debugging".')
      sys.exit(1)
    except:
      import traceback
      traceback.print_exc()
      self.Close()
      raise

  def GetBrowserStartupArgs(self):
    args = super(AndroidBrowserBackend, self).GetBrowserStartupArgs()
    args.append('--enable-remote-debugging')
    args.append('--no-restore-state')
    args.append('--disable-fre')
    return args

  @property
  def adb(self):
    return self._adb

  @property
  def pid(self):
    return int(self._adb.ExtractPid(self._backend_settings.package)[0])

  def __del__(self):
    self.Close()

  def Close(self):
    super(AndroidBrowserBackend, self).Close()

    if self._saved_cmdline:
      self._adb.Adb().SetProtectedFileContents(
          self._backend_settings.cmdline_file,
          self._saved_cmdline)
    else:
      self._adb.RunShellCommand('rm %s' % self._backend_settings.cmdline_file)
    self._adb.CloseApplication(self._backend_settings.package)

  def IsBrowserRunning(self):
    pids = self._adb.ExtractPid(self._backend_settings.package)
    return len(pids) != 0

  def GetRemotePort(self, local_port):
    return local_port

  def GetStandardOutput(self):
    # If we can find symbols and there is a stack, output the symbolized stack.
    symbol_paths = [
        os.path.join(adb_commands.GetOutDirectory(), 'Release', 'lib'),
        os.path.join(adb_commands.GetOutDirectory(), 'Debug', 'lib'),
        os.path.join(adb_commands.GetOutDirectory(), 'Release', 'lib.target'),
        os.path.join(adb_commands.GetOutDirectory(), 'Debug', 'lib.target')]
    for symbol_path in symbol_paths:
      if not os.path.isdir(symbol_path):
        continue
      with tempfile.NamedTemporaryFile() as f:
        lines = self._adb.RunShellCommand('logcat -d')
        for line in lines:
          f.write(line + '\n')
        symbolized_stack = None
        try:
          logging.info('Symbolizing stack...')
          symbolized_stack = subprocess.Popen([
              'ndk-stack', '-sym', symbol_path,
              '-dump', f.name], stdout=subprocess.PIPE).communicate()[0]
        except Exception:
          pass
        if symbolized_stack:
          return symbolized_stack
    # Otherwise, just return the last 100 lines of logcat.
    return '\n'.join(self._adb.RunShellCommand('logcat -d -t 100'))

  def CreateForwarder(self, *port_pairs):
    return adb_commands.Forwarder(self._adb, *port_pairs)
