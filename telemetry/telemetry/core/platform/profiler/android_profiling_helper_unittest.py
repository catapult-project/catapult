# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import glob
import os
import re
import shutil
import tempfile

from telemetry import test
from telemetry.core import util
from telemetry.core.platform.profiler import android_profiling_helper
from telemetry.unittest import simple_mock
from telemetry.unittest import tab_test_case


def _GetLibrariesMappedIntoProcesses(device, pids):
  libs = set()
  for pid in pids:
    maps_file = '/proc/%d/maps' % pid
    maps = device.old_interface.GetProtectedFileContents(maps_file)
    for map_line in maps:
      lib = re.match(r'.*\s(/.*[.]so)$', map_line)
      if lib:
        libs.add(lib.group(1))
  return libs


class TestAndroidProfilingHelper(tab_test_case.TabTestCase):
  def setUp(self):
    super(TestAndroidProfilingHelper, self).setUp()
    # pylint: disable=W0212
    browser_backend = self._browser._browser_backend
    try:
      self._device = browser_backend.adb.device()
    except AttributeError:
      pass

  def testGetRequiredLibrariesForPerfProfile(self):
    perf_output = os.path.join(
        util.GetUnittestDataDir(), 'sample_perf_report_output.txt')
    with open(perf_output) as f:
      perf_output = f.read()

    mock_popen = simple_mock.MockObject()
    mock_popen.ExpectCall('communicate').WillReturn([None, perf_output])

    mock_subprocess = simple_mock.MockObject()
    mock_subprocess.ExpectCall(
        'Popen').WithArgs(simple_mock.DONT_CARE).WillReturn(mock_popen)
    mock_subprocess.SetAttribute('PIPE', simple_mock.MockObject())

    real_subprocess = android_profiling_helper.subprocess
    android_profiling_helper.subprocess = mock_subprocess
    try:
      libs = android_profiling_helper.GetRequiredLibrariesForPerfProfile('foo')
      self.assertEqual(libs, set([
          '/data/app-lib/com.google.android.apps.chrome-2/libchrome.2016.0.so',
          '/system/lib/libart.so',
          '/system/lib/libc.so',
          '/system/lib/libm.so']))
    finally:
      android_profiling_helper.subprocess = real_subprocess

  @test.Enabled('android')
  def testCreateSymFs(self):
    # pylint: disable=W0212
    browser_pid = self._browser._browser_backend.pid
    pids = ([browser_pid] +
        self._browser._platform_backend.GetChildPids(browser_pid))
    libs = _GetLibrariesMappedIntoProcesses(self._device, pids)
    assert libs

    symfs_dir = tempfile.mkdtemp()
    try:
      kallsyms = android_profiling_helper.CreateSymFs(self._device, symfs_dir,
                                                      libs)

      # Make sure we found at least one unstripped library.
      unstripped_libs = glob.glob(os.path.join(symfs_dir,
                                               'data', 'app-lib', '*', '*.so'))
      assert unstripped_libs

      # Check that we have kernel symbols.
      assert os.path.exists(kallsyms)

      # Check that all requested libraries are present.
      for lib in libs:
        assert os.path.exists(os.path.join(symfs_dir, lib[1:])), \
            '%s not found in symfs' % lib
    finally:
      shutil.rmtree(symfs_dir)

  @test.Enabled('android')
  def testGetToolchainBinaryPath(self):
    with tempfile.NamedTemporaryFile() as libc:
      self._device.old_interface.PullFileFromDevice('/system/lib/libc.so',
                                                    libc.name)
      path = android_profiling_helper.GetToolchainBinaryPath(libc.name,
                                                             'objdump')
      assert os.path.exists(path)
