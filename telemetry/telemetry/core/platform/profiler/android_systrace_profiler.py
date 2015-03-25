# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import StringIO
import subprocess
import zipfile

from telemetry.core.backends.chrome import android_browser_finder
from telemetry.core.platform import profiler
from telemetry.core.platform import tracing_options
from telemetry.core import util
from telemetry.timeline import trace_data as trace_data_module

_SYSTRACE_CATEGORIES = [
    'gfx',
    'input',
    'view',
    'sched',
    'freq',
]

class AndroidSystraceProfiler(profiler.Profiler):
  """Collects a Systrace on Android."""

  def __init__(self, browser_backend, platform_backend, output_path, state,
               device=None):
    super(AndroidSystraceProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)
    assert self._browser_backend.supports_tracing
    self._output_path = output_path + '-trace.zip'
    self._systrace_output_path = output_path + '.systrace'

    # Use telemetry's own tracing backend instead the combined mode in
    # adb_profile_chrome because some benchmarks also do tracing of their own
    # and the two methods conflict.
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    self._browser_backend.StartTracing(options, timeout=10)
    command = ['python', os.path.join(util.GetChromiumSrcDir(), 'tools',
                                      'profile_chrome.py'),
               '--categories', '', '--continuous', '--output',
               self._systrace_output_path, '--json', '--systrace',
               ','.join(_SYSTRACE_CATEGORIES)]
    if device:
      command.extend(['--device', device])
    self._profiler = subprocess.Popen(command, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)

  @classmethod
  def name(cls):
    return 'android-systrace'

  @classmethod
  def is_supported(cls, browser_type):
    if browser_type == 'any':
      return android_browser_finder.CanFindAvailableBrowsers()
    return browser_type.startswith('android')

  def CollectProfile(self):
    self._profiler.communicate(input='\n')
    trace_result_builder = trace_data_module.TraceDataBuilder()
    self._browser_backend.StopTracing(trace_result_builder)
    trace_result = trace_result_builder.AsData()

    trace_file = StringIO.StringIO()
    trace_result.Serialize(trace_file)

    # Merge the chrome and systraces into a zip file.
    with zipfile.ZipFile(self._output_path, 'w', zipfile.ZIP_DEFLATED) as z:
      z.writestr('trace.json', trace_file.getvalue())
      z.write(self._systrace_output_path, 'systrace')
      os.unlink(self._systrace_output_path)

    print 'Systrace saved as %s' % self._output_path
    print 'To view, open in chrome://tracing'
    return [self._output_path]
