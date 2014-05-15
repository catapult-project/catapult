# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys

from telemetry.core.platform.profiler import vtune_profiler
from telemetry.unittest import options_for_unittests
from telemetry.unittest import simple_mock
from telemetry.unittest import tab_test_case

class MockPopen(object):
  def __init__(self, returncode, stdout=None, stderr=None):
    self.returncode = returncode
    self.stdout = stdout
    self.stderr = stderr

  def communicate(self):
    return (self.stdout, self.stderr)

  def wait(self):
    return self.returncode


class TestVTuneProfiler(tab_test_case.TabTestCase):
  def setUp(self):
    super(TestVTuneProfiler, self).setUp()

  def testVTuneProfilerIsSupported(self):
    options = options_for_unittests.GetCopy()

    mock_subprocess = simple_mock.MockObject()
    mock_subprocess.ExpectCall(
        'Popen').WithArgs(simple_mock.DONT_CARE).WillReturn(MockPopen(0))
    mock_subprocess.SetAttribute('PIPE', simple_mock.MockObject())
    mock_subprocess.SetAttribute('STDOUT', simple_mock.MockObject())

    real_subprocess = vtune_profiler.subprocess
    vtune_profiler.subprocess = mock_subprocess

    if options.browser_type.startswith('android'):
      # On Android we're querying if 'su' is available.
      mock_subprocess.ExpectCall('Popen').WithArgs(
          simple_mock.DONT_CARE).WillReturn(MockPopen(0, 'su', None))

    try:
      self.assertTrue(
          vtune_profiler.VTuneProfiler.is_supported(options.browser_type) or
          sys.platform != 'linux2' or
          options.browser_type.startswith('cros'))
    finally:
      vtune_profiler.subprocess = real_subprocess

  def _ComputeNumProcesses(self, browser_backend, platform_backend):
    # Compute the number of processes that will be profiled by VTune:
    # If we have renderer processes, each of them will be profiled, otherwise
    # we profile the browser process.
    pids = ([browser_backend.pid] +
            platform_backend.GetChildPids(browser_backend.pid))
    cmd_lines = [ platform_backend.GetCommandLine(p) for p in pids ]
    process_names = [ browser_backend.GetProcessName(cl) for cl in cmd_lines ]

    return max(1, process_names.count('renderer'))

  def testVTuneProfiler(self):
    mock_subprocess = simple_mock.MockObject()
    mock_subprocess.SetAttribute('PIPE', simple_mock.MockObject())
    mock_subprocess.SetAttribute('STDOUT', simple_mock.MockObject())

    # For each profiled process, expect one call to start VTune and one to stop
    # it.
    # pylint: disable=W0212
    num_processes = self._ComputeNumProcesses(self._browser._browser_backend,
                                              self._browser._platform_backend)
    for _ in xrange(num_processes):
      mock_subprocess.ExpectCall(
          'Popen').WithArgs(simple_mock.DONT_CARE).WillReturn(MockPopen(0))
    for _ in xrange(num_processes):
      mock_subprocess.ExpectCall('call').WithArgs(simple_mock.DONT_CARE)

    real_subprocess = vtune_profiler.subprocess
    vtune_profiler.subprocess = mock_subprocess

    try:
      # pylint: disable=W0212
      profiler = vtune_profiler.VTuneProfiler(self._browser._browser_backend,
                                              self._browser._platform_backend,
                                              'tmp',
                                              {})
      profiler.CollectProfile()
    finally:
      vtune_profiler.subprocess = real_subprocess
