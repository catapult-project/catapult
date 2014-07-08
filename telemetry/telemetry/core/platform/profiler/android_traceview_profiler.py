# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util
from telemetry.core.backends.chrome import android_browser_finder
from telemetry.core.platform import profiler


class AndroidTraceviewProfiler(profiler.Profiler):
  """Collects a Traceview on Android."""

  _DEFAULT_DEVICE_DIR = '/data/local/tmp/traceview'

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(AndroidTraceviewProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)

    if self._browser_backend.adb.device().FileExists(self._DEFAULT_DEVICE_DIR):
      self._browser_backend.adb.RunShellCommand(
          'rm ' + os.path.join(self._DEFAULT_DEVICE_DIR, '*'))
    else:
      self._browser_backend.adb.RunShellCommand(
          'mkdir -p ' + self._DEFAULT_DEVICE_DIR)
      self._browser_backend.adb.RunShellCommand(
          'chmod 777 ' + self._DEFAULT_DEVICE_DIR)

    self._trace_files = []
    for pid in self._GetProcessOutputFileMap().iterkeys():
      device_dump_file = '%s/%s.trace' % (self._DEFAULT_DEVICE_DIR, pid)
      self._trace_files.append((pid, device_dump_file))
      self._browser_backend.adb.RunShellCommand('am profile %s start %s' %
                                                (pid, device_dump_file))


  @classmethod
  def name(cls):
    return 'android-traceview'

  @classmethod
  def is_supported(cls, browser_type):
    if browser_type == 'any':
      return android_browser_finder.CanFindAvailableBrowsers()
    return browser_type.startswith('android')

  def CollectProfile(self):
    output_files = []
    for pid, trace_file in self._trace_files:
      self._browser_backend.adb.RunShellCommand('am profile %s stop' % pid)
      util.WaitFor(lambda: self._FileSize(trace_file) > 0, timeout=10)
      output_files.append(trace_file)
    self._browser_backend.adb.device().old_interface.Adb().Pull(
        self._DEFAULT_DEVICE_DIR, self._output_path)
    self._browser_backend.adb.RunShellCommand(
        'rm ' + os.path.join(self._DEFAULT_DEVICE_DIR, '*'))
    print 'Traceview profiles available in ', self._output_path
    print 'Use third_party/android_tools/sdk/tools/monitor '
    print 'then use "File->Open File" to visualize them.'
    return output_files

  def _FileSize(self, file_name):
    f = self._browser_backend.adb.device().Ls(file_name)
    return f.get(os.path.basename(file_name), (0, ))[0]
