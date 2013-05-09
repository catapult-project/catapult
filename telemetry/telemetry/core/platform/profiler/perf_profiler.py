# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import signal
import subprocess
import sys
import tempfile

from telemetry.core.platform import profiler


class PerfProfiler(profiler.Profiler):

  def __init__(self, pid, output_path):
    super(PerfProfiler, self).__init__(output_path)
    self._tmp_output_file = tempfile.NamedTemporaryFile('w', 0)
    self._proc = subprocess.Popen(
        ['perf', 'record', '--call-graph',
         '--pid', str(pid), '--output', self.output_path],
        stdout=self._tmp_output_file, stderr=subprocess.STDOUT)

  @classmethod
  def name(cls):
    return 'perf'

  @classmethod
  def is_supported(cls, options):
    return (sys.platform == 'linux2'
            and not options.browser_type.startswith('android')
            and not options.browser_type.startswith('cros'))

  def CollectProfile(self):
    self._proc.send_signal(signal.SIGINT)
    exit_code = self._proc.wait()
    try:
      if exit_code not in (0, -2):
        raise Exception(
            'perf failed with exit code %d. Output:\n%s' % (exit_code,
                                                            self._GetStdOut()))
    finally:
      self._proc = None
      self._tmp_output_file.close()

    print 'To view the profile, run:'
    print '  perf report -i %s' % self.output_path

  def _GetStdOut(self):
    self._tmp_output_file.flush()
    try:
      with open(self._tmp_output_file.name) as f:
        return f.read()
    except IOError:
      return ''
