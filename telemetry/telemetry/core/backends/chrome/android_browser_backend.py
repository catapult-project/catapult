# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import subprocess
import sys
import time

from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import util
from telemetry.core.backends import adb_commands
from telemetry.core.backends import browser_backend
from telemetry.core.backends.chrome import chrome_browser_backend
from telemetry.core.forwarders import android_forwarder

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib.device import device_errors  # pylint: disable=F0401
from pylib.device import intent  # pylint: disable=F0401


class AndroidBrowserBackendSettings(object):

  def __init__(self, adb, activity, cmdline_file, package, pseudo_exec_name,
               supports_tab_control):
    self.adb = adb
    self.activity = activity
    self.cmdline_file = cmdline_file
    self.package = package
    self.pseudo_exec_name = pseudo_exec_name
    self.supports_tab_control = supports_tab_control

  def GetDevtoolsRemotePort(self):
    raise NotImplementedError()

  def RemoveProfile(self):
    files = self.adb.device().RunShellCommand(
        'ls "%s"' % self.profile_dir, as_root=True)
    # Don't delete lib, since it is created by the installer.
    paths = ['"%s/%s"' % (self.profile_dir, f) for f in files if f != 'lib']
    self.adb.device().RunShellCommand('rm -r %s' % ' '.join(paths),
                                      as_root=True)

  def PushProfile(self, _):
    logging.critical('Profiles cannot be overriden with current configuration')
    sys.exit(1)

  @property
  def profile_dir(self):
    return '/data/data/%s/' % self.package


class ChromeBackendSettings(AndroidBrowserBackendSettings):
  # Stores a default Preferences file, re-used to speed up "--page-repeat".
  _default_preferences_file = None

  @staticmethod
  def _GetCommandLineFile(adb):
    if adb.IsUserBuild():
      return '/data/local/tmp/chrome-command-line'
    else:
      return '/data/local/chrome-command-line'

  def __init__(self, adb, package):
    super(ChromeBackendSettings, self).__init__(
        adb=adb,
        activity='com.google.android.apps.chrome.Main',
        cmdline_file=ChromeBackendSettings._GetCommandLineFile(adb),
        package=package,
        pseudo_exec_name='chrome',
        supports_tab_control=True)

  def GetDevtoolsRemotePort(self):
    return 'localabstract:chrome_devtools_remote'

  def PushProfile(self, new_profile_dir):
    # Pushing the profile is slow, so we don't want to do it every time.
    # Avoid this by pushing to a safe location using PushChangedFiles, and
    # then copying into the correct location on each test run.

    (profile_parent, profile_base) = os.path.split(new_profile_dir)
    # If the path ends with a '/' python split will return an empty string for
    # the base name; so we now need to get the base name from the directory.
    if not profile_base:
      profile_base = os.path.basename(profile_parent)

    saved_profile_location = '/sdcard/profile/%s' % profile_base
    self.adb.device().PushChangedFiles(new_profile_dir, saved_profile_location)

    self.adb.device().old_interface.EfficientDeviceDirectoryCopy(
        saved_profile_location, self.profile_dir)
    dumpsys = self.adb.device().RunShellCommand(
        'dumpsys package %s' % self.package)
    id_line = next(line for line in dumpsys if 'userId=' in line)
    uid = re.search('\d+', id_line).group()
    files = self.adb.device().RunShellCommand(
        'ls "%s"' % self.profile_dir, as_root=True)
    files.remove('lib')
    paths = ['%s/%s' % (self.profile_dir, f) for f in files]
    for path in paths:
      extended_path = '%s %s/* %s/*/* %s/*/*/*' % (path, path, path, path)
      self.adb.device().RunShellCommand(
          'chown %s.%s %s' % (uid, uid, extended_path))

class ContentShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(ContentShellBackendSettings, self).__init__(
        adb=adb,
        activity='org.chromium.content_shell_apk.ContentShellActivity',
        cmdline_file='/data/local/tmp/content-shell-command-line',
        package=package,
        pseudo_exec_name='content_shell',
        supports_tab_control=False)

  def GetDevtoolsRemotePort(self):
    return 'localabstract:content_shell_devtools_remote'


class ChromeShellBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(ChromeShellBackendSettings, self).__init__(
          adb=adb,
          activity='org.chromium.chrome.shell.ChromeShellActivity',
          cmdline_file='/data/local/tmp/chrome-shell-command-line',
          package=package,
          pseudo_exec_name='chrome_shell',
          supports_tab_control=False)

  def GetDevtoolsRemotePort(self):
    return 'localabstract:chrome_shell_devtools_remote'


class WebviewBackendSettings(AndroidBrowserBackendSettings):
  def __init__(self, adb, package):
    super(WebviewBackendSettings, self).__init__(
        adb=adb,
        activity='com.android.webview.chromium.shell.TelemetryActivity',
        cmdline_file='/data/local/tmp/webview-command-line',
        package=package,
        pseudo_exec_name='webview',
        supports_tab_control=False)

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
        raise exceptions.BrowserGoneException(self.browser,
                                              'Timeout waiting for PID.')
    return 'localabstract:webview_devtools_remote_%s' % str(pid)


class AndroidBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  """The backend for controlling a browser instance running on Android."""
  def __init__(self, browser_options, backend_settings, use_rndis_forwarder,
               output_profile_path, extensions_to_load):
    super(AndroidBrowserBackend, self).__init__(
        supports_tab_control=backend_settings.supports_tab_control,
        supports_extensions=False, browser_options=browser_options,
        output_profile_path=output_profile_path,
        extensions_to_load=extensions_to_load)
    if len(extensions_to_load) > 0:
      raise browser_backend.ExtensionsNotSupportedException(
          'Android browser does not support extensions.')

    # Initialize fields so that an explosion during init doesn't break in Close.
    self._adb = backend_settings.adb
    self._backend_settings = backend_settings
    self._saved_cmdline = ''

    # TODO(tonyg): This is flaky because it doesn't reserve the port that it
    # allocates. Need to fix this.
    self._port = adb_commands.AllocateTestServerPort()

    # Kill old browser.
    self._adb.device().ForceStop(self._backend_settings.package)

    if self._adb.device().old_interface.CanAccessProtectedFileContents():
      if self.browser_options.profile_dir:
        self._backend_settings.PushProfile(self.browser_options.profile_dir)
      elif not self.browser_options.dont_override_profile:
        self._backend_settings.RemoveProfile()

    self._forwarder_factory = android_forwarder.AndroidForwarderFactory(
        self._adb, use_rndis_forwarder)

    if self.browser_options.netsim:
      assert use_rndis_forwarder, 'Netsim requires RNDIS forwarding.'
      self.wpr_port_pairs = forwarders.PortPairs(
          http=forwarders.PortPair(0, 80),
          https=forwarders.PortPair(0, 443),
          dns=forwarders.PortPair(0, 53))

    # Set the debug app if needed.
    if self._adb.IsUserBuild():
      logging.debug('User build device, setting debug app')
      self._adb.device().RunShellCommand(
          'am set-debug-app --persistent %s' % self._backend_settings.package)

  def _SetUpCommandLine(self):
    def QuoteIfNeeded(arg):
      # Escape 'key=valueA valueB' to 'key="valueA valueB"'
      # Already quoted values, or values without space are left untouched.
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
      return '%s="%s"' % (key, values)
    args = [self._backend_settings.pseudo_exec_name]
    args.extend(self.GetBrowserStartupArgs())
    args = ' '.join(map(QuoteIfNeeded, args))

    self._SetCommandLineFile(args)

  def _SetCommandLineFile(self, file_contents):
    logging.debug('Using command line: ' + file_contents)
    def IsProtectedFile(name):
      if self._adb.device().old_interface.FileExistsOnDevice(name):
        return not self._adb.device().old_interface.IsFileWritableOnDevice(name)
      else:
        parent_name = os.path.dirname(name)
        if parent_name != '':
          return IsProtectedFile(parent_name)
        else:
          return True

    protected = IsProtectedFile(self._backend_settings.cmdline_file)
    try:
      self._saved_cmdline = ''.join(
          self._adb.device().ReadFile(
              self._backend_settings.cmdline_file, as_root=protected)
          or [])
      self._adb.device().WriteFile(
          self._backend_settings.cmdline_file, file_contents,
          as_root=protected)
    except device_errors.CommandFailedError:
      logging.critical('Cannot set Chrome command line. '
                       'Fix this by flashing to a userdebug build.')
      sys.exit(1)

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
    self._adb.device().old_interface.DismissCrashDialogIfNeeded()
    self._adb.device().StartActivity(
        intent.Intent(package=self._backend_settings.package,
                      activity=self._backend_settings.activity,
                      action=None, data=url, category=None),
        blocking=True)

    self._adb.Forward('tcp:%d' % self._port,
                      self._backend_settings.GetDevtoolsRemotePort())

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
      # Restore the saved command line if it appears to have come from a user.
      # If it appears to be a Telemetry created command line, then don't restore
      # it. This is to prevent a common bug where --host-resolver-rules borks
      # people's browsers if something goes wrong with Telemetry.
      self._SetCommandLineFile(
          self._saved_cmdline
          if '--host-resolver-rules' not in self._saved_cmdline else '')

  def GetBrowserStartupArgs(self):
    args = super(AndroidBrowserBackend, self).GetBrowserStartupArgs()
    if self.forwarder_factory.does_forwarder_override_dns:
      args = [arg for arg in args
              if not arg.startswith('--host-resolver-rules')]
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
    self._adb.device().ForceStop(self._backend_settings.package)

    if self._output_profile_path:
      logging.info("Pulling profile directory from device: '%s'->'%s'.",
                   self._backend_settings.profile_dir,
                   self._output_profile_path)
      # To minimize bandwidth it might be good to look at whether all the data
      # pulled down is really needed e.g. .pak files.
      if not os.path.exists(self._output_profile_path):
        os.makedirs(self._output_profile_pathame)
      files = self.adb.device().RunShellCommand(
          'ls "%s"' % self._backend_settings.profile_dir)
      for f in files:
        # Don't pull lib, since it is created by the installer.
        if f != 'lib':
          source = '%s%s' % (self._backend_settings.profile_dir, f)
          dest = os.path.join(self._output_profile_path, f)
          # self._adb.Pull(source, dest) doesn't work because its timeout
          # is fixed in android's adb_interface at 60 seconds, which may
          # be too short to pull the cache.
          cmd = 'pull %s %s' % (source, dest)
          self._adb.device().old_interface.Adb().SendCommand(
              cmd, timeout_time=240)

  def IsBrowserRunning(self):
    pids = self._adb.ExtractPid(self._backend_settings.package)
    return len(pids) != 0

  def GetRemotePort(self, local_port):
    return local_port

  def GetStandardOutput(self):
    return '\n'.join(self._adb.device().RunShellCommand('logcat -d -t 500'))

  def GetStackTrace(self):
    def Decorate(title, content):
      return title + '\n' + content + '\n' + '*' * 80 + '\n'
    # Get the last lines of logcat (large enough to contain stacktrace)
    logcat = self.GetStandardOutput()
    ret = Decorate('Logcat', logcat)
    stack = os.path.join(util.GetChromiumSrcDir(), 'third_party',
                         'android_platform', 'development', 'scripts', 'stack')
    # Try to symbolize logcat.
    if os.path.exists(stack):
      p = subprocess.Popen([stack], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE)
      ret += Decorate('Stack from Logcat', p.communicate(input=logcat)[0])

    # Try to get tombstones.
    tombstones = os.path.join(util.GetChromiumSrcDir(), 'build', 'android',
                              'tombstones.py')
    if os.path.exists(tombstones):
      ret += Decorate('Tombstones',
                      subprocess.Popen([tombstones, '-w', '--device',
                                        self._adb.device_serial()],
                                       stdout=subprocess.PIPE).communicate()[0])
    return ret

  def AddReplayServerOptions(self, extra_wpr_args):
    if not self.forwarder_factory.does_forwarder_override_dns:
      extra_wpr_args.append('--no-dns_forwarding')
    if self.browser_options.netsim:
      extra_wpr_args.append('--net=%s' % self.browser_options.netsim)
