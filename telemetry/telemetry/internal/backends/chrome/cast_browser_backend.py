# Copyright 2022 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from telemetry.internal.backends.chrome import chrome_browser_backend

DEVTOOLS_PORT = 9222

class ReceiverNotFoundException(Exception):
  pass


class CastBrowserBackend(chrome_browser_backend.ChromeBrowserBackend):
  def __init__(self, cast_platform_backend, browser_options,
               browser_directory, profile_directory, casting_tab):
    super(CastBrowserBackend, self).__init__(
        cast_platform_backend,
        browser_options=browser_options,
        browser_directory=browser_directory,
        profile_directory=profile_directory,
        supports_extensions=False,
        supports_tab_control=False)
    self._browser_process = None
    self._cast_core_process = None
    self._casting_tab = casting_tab
    self._output_dir = cast_platform_backend.output_dir
    self._receiver_name = None

  @property
  def log_file_path(self):
    return None

  def _FindDevToolsPortAndTarget(self):
    return DEVTOOLS_PORT, None

  def _ReadReceiverName(self):
    raise NotImplementedError

  def Start(self, startup_args):
    raise NotImplementedError

  def _WaitForSink(self, timeout=60):
    sink_name_list = []
    start_time = time.time()
    while (self._receiver_name not in sink_name_list
           and time.time() - start_time < timeout):
      self._casting_tab.action_runner.tab.EnableCast()
      sink_name_list = [
          sink['name'] for sink in self._casting_tab\
                                       .action_runner.tab.GetCastSinks()
      ]
      self._casting_tab.action_runner.Wait(1)
    if self._receiver_name not in sink_name_list:
      raise ReceiverNotFoundException(
          'Could not find Cast Receiver {0}.'.format(self._receiver_name))

  def GetReceiverName(self):
    return self._receiver_name

  def GetPid(self):
    return self._browser_process.pid

  def Close(self):
    super(CastBrowserBackend, self).Close()
    if self._browser_process:
      logging.info('Shutting down Cast browser.')
      self._browser_process = None
    if self._cast_core_process:
      self._cast_core_process.kill()
      self._cast_core_process = None

  def IsBrowserRunning(self):
    return bool(self._browser_process)

  def GetStandardOutput(self):
    return 'Stdout is not available for Cast browser.'

  def GetStackTrace(self):
    return (False, 'Stack trace is not yet supported on Cast browser.')

  def SymbolizeMinidump(self, minidump_path):
    logging.info('Symbolizing Minidump is not yet supported on Cast browser.')
    return None
