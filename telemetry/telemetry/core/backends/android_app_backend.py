# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import time

from telemetry.core import android_process
from telemetry.core.backends import adb_commands
from telemetry.core.backends import android_browser_backend_settings
from telemetry.core.backends import android_command_line_backend
from telemetry.core.backends import app_backend
from telemetry.core import util
from telemetry.core import web_contents


class AndroidAppBackend(app_backend.AppBackend):

  def __init__(self, android_platform_backend, start_intent,
               is_app_ready_predicate=None):
    super(AndroidAppBackend, self).__init__(
        start_intent.package, android_platform_backend)
    self._default_process_name = start_intent.package
    self._start_intent = start_intent
    self._is_app_ready_predicate = is_app_ready_predicate
    self._is_running = False
    self._existing_processes_by_pid = {}

  @property
  def _adb(self):
    return self.platform_backend.adb

  def _IsAppReady(self):
    if self._is_app_ready_predicate is None:
      return True
    return self._is_app_ready_predicate(self.app)

  def Start(self):
    """Start an Android app and wait for it to finish launching.

    AppStory derivations can customize the wait-for-ready-state to wait
    for a more specific event if needed.
    """
    webview_startup_args = self.GetWebviewStartupArgs()
    backend_settings = android_browser_backend_settings.WebviewBackendSettings(
        'android-webview')
    with android_command_line_backend.SetUpCommandLineFlags(
        self._adb, backend_settings, webview_startup_args):
      # TODO(slamm): check if can use "blocking=True" instead of needing to
      # sleep. If "blocking=True" does not work, switch sleep to "ps" check.
      self._adb.device().StartActivity(self._start_intent, blocking=False)
      util.WaitFor(self._IsAppReady, timeout=60)
    self._is_running = True

  def Close(self):
    self._is_running = False
    self.platform_backend.KillApplication(self._start_intent.package)

  def IsAppRunning(self):
    return self._is_running

  def GetStandardOutput(self):
    raise NotImplementedError

  def GetStackTrace(self):
    raise NotImplementedError

  def GetProcesses(self, process_filter=None):
    if process_filter is None:
      process_filter = lambda n: re.match('^' + self._default_process_name, n)

    processes = set()
    ps_output = self.platform_backend.GetPsOutput(['pid', 'name'])
    for pid, name in ps_output:
      if not process_filter(name):
        continue

      if pid not in self._existing_processes_by_pid:
        self._existing_processes_by_pid[pid] = android_process.AndroidProcess(
            self, pid, name)
      processes.add(self._existing_processes_by_pid[pid])
    return processes

  def GetProcess(self, subprocess_name):
    assert subprocess_name.startswith(':')
    process_name = self._default_process_name + subprocess_name
    return self.GetProcesses(lambda n: n == process_name).pop()

  def GetWebViews(self):
    webviews = set()
    for process in self.GetProcesses():
      webviews.update(process.GetWebViews())
    return webviews

  def GetWebviewStartupArgs(self):
    args = []

    # Turn on GPU benchmarking extension for all runs. The only side effect of
    # the extension being on is that render stats are tracked. This is believed
    # to be effectively free. And, by doing so here, it avoids us having to
    # programmatically inspect a pageset's actions in order to determine if it
    # might eventually scroll.
    args.append('--enable-gpu-benchmarking')

    return args
