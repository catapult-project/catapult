# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import subprocess
import sys
import tempfile
import time

from telemetry import adb_commands
from telemetry import browser_backend
from telemetry import browser_gone_exception

class AndroidBrowserBackend(browser_backend.BrowserBackend):
  """The backend for controlling a browser instance running on Android.
  """
  def __init__(self, options, adb, package,
               is_content_shell, cmdline_file, activity, devtools_remote_port):
    super(AndroidBrowserBackend, self).__init__(is_content_shell, options)
    # Initialize fields so that an explosion during init doesn't break in Close.
    self._options = options
    self._adb = adb
    self._package = package
    self._cmdline_file = cmdline_file
    self._activity = activity
    if not options.keep_test_server_ports:
      adb_commands.ResetTestServerPortAllocation()
    self._port = adb_commands.AllocateTestServerPort()
    self._devtools_remote_port = devtools_remote_port

    # Kill old browser.
    self._adb.CloseApplication(self._package)
    self._adb.KillAll('device_forwarder')
    self._adb.Forward('tcp:%d' % self._port, self._devtools_remote_port)

    # Chrome Android doesn't listen to --user-data-dir.
    # TODO: symlink the app's Default, files and cache dir
    # to somewhere safe.
    if not is_content_shell and not options.dont_override_profile:
      # Set up the temp dir
      # self._tmpdir = '/sdcard/telemetry_data'
      # self._adb.RunShellCommand('rm -r %s' %  self._tmpdir)
      # args.append('--user-data-dir=%s' % self._tmpdir)
      pass

    # Set up the command line.
    if is_content_shell:
      pseudo_exec_name = 'content_shell'
    else:
      pseudo_exec_name = 'chrome'

    args = [pseudo_exec_name]
    args.extend(self.GetBrowserStartupArgs())

    with tempfile.NamedTemporaryFile() as f:
      def EscapeIfNeeded(arg):
        params = arg.split('=')
        if (len(params) == 2 and
            params[1] and params[1][0] == '"' and params[1][-1] == '"'):
          # CommandLine.java requires this extra escaping.
          return '%s="\\%s\\"' % (params[0], params[1])
        return arg.replace(' ', '" "')
      f.write(' '.join([EscapeIfNeeded(arg) for arg in args]))
      f.flush()
      self._adb.Push(f.name, cmdline_file)

    # Force devtools protocol on, if not already done.
    if not is_content_shell and self._adb.IsRootEnabled():
      # Make sure we can find the apps' prefs file
      app_data_dir = '/data/data/%s' % self._package
      prefs_file = (app_data_dir +
                    '/app_chrome/Default/Preferences')
      if not self._adb.FileExistsOnDevice(prefs_file):
        # Start it up the first time so we can tweak the prefs.
        self._adb.StartActivity(self._package,
                                self._activity,
                                True,
                                None,
                                None)
        retries = 0
        while not self._adb.Adb().GetFileContents(prefs_file):
          time.sleep(3)
          retries += 1
          if retries == 3:
            logging.critical('android_browser_backend: Could not find '
                             'preferences file %s for %s',
                             prefs_file, self._package)
            raise browser_gone_exception.BrowserGoneException(
                'Missing preferences file.')
        self._adb.KillAll(self._package)

      with tempfile.NamedTemporaryFile() as raw_f:
        self._adb.Pull(prefs_file, raw_f.name)
        with open(raw_f.name, 'r') as f:
          txt_in = f.read()
          preferences = json.loads(txt_in)
        changed = False
        if 'devtools' not in preferences:
          preferences['devtools'] = {}
          changed = True
        if 'remote_enabled' not in preferences['devtools']:
          preferences['devtools']['remote_enabled'] = True
          changed = True
        if preferences['devtools']['remote_enabled'] != True:
          preferences['devtools']['remote_enabled'] = True
          changed = True
        if changed:
          logging.warning('Manually enabled devtools protocol on %s' %
                          self._package)
          with open(raw_f.name, 'w') as f:
            txt = json.dumps(preferences, indent=2)
            f.write(txt)
          self._adb.Push(raw_f.name, prefs_file)

    # Start it up with a fresh log.
    self._adb.RunShellCommand('logcat -c')
    self._adb.StartActivity(self._package,
                            self._activity,
                            True,
                            None,
                            'chrome://newtab/')
    try:
      self._WaitForBrowserToComeUp()
      self._PostBrowserStartupInitialization()
    except browser_gone_exception.BrowserGoneException:
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
    args.append('--disable-fre')
    return args

  def __del__(self):
    self.Close()

  def Close(self):
    super(AndroidBrowserBackend, self).Close()

    self._adb.RunShellCommand('rm %s' % self._cmdline_file)
    self._adb.CloseApplication(self._package)

  def IsBrowserRunning(self):
    pids = self._adb.ExtractPid(self._package)
    return len(pids) != 0

  def GetStandardOutput(self):
    # If we can find symbols and there is a stack, output the symbolized stack.
    symbol_paths = [
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
