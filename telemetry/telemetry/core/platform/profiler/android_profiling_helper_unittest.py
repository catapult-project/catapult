# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import pickle
import re
import shutil
import tempfile
import unittest

from telemetry.core.platform.profiler import android_profiling_helper
from telemetry.core import util
from telemetry import decorators
from telemetry.unittest_util import simple_mock
from telemetry.unittest_util import tab_test_case


def _GetLibrariesMappedIntoProcesses(device, pids):
  libs = set()
  for pid in pids:
    maps_file = '/proc/%d/maps' % pid
    maps = device.ReadFile(maps_file, as_root=True).splitlines()
    for map_line in maps:
      lib = re.match(r'.*\s(/.*[.]so)$', map_line)
      if lib:
        libs.add(lib.group(1))
  return libs


class TestAndroidProfilingHelper(unittest.TestCase):

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

  @decorators.Enabled('android')
  def testGetRequiredLibrariesForVTuneProfile(self):
    vtune_db_output = os.path.join(
        util.GetUnittestDataDir(), 'sample_vtune_db_output')
    with open(vtune_db_output, 'rb') as f:
      vtune_db_output = pickle.load(f)

    mock_cursor = simple_mock.MockObject()
    mock_cursor.ExpectCall(
        'execute').WithArgs(simple_mock.DONT_CARE).WillReturn(vtune_db_output)

    mock_conn = simple_mock.MockObject()
    mock_conn.ExpectCall('cursor').WillReturn(mock_cursor)
    mock_conn.ExpectCall('close')

    mock_sqlite3 = simple_mock.MockObject()
    mock_sqlite3.ExpectCall(
        'connect').WithArgs(simple_mock.DONT_CARE).WillReturn(mock_conn)

    real_sqlite3 = android_profiling_helper.sqlite3
    android_profiling_helper.sqlite3 = mock_sqlite3
    try:
      libs = android_profiling_helper.GetRequiredLibrariesForVTuneProfile('foo')
      self.assertEqual(libs, set([
          '/data/app-lib/com.google.android.apps.chrome-1/libchrome.2019.0.so',
          '/system/lib/libdvm.so',
          '/system/lib/libc.so',
          '/system/lib/libm.so']))
    finally:
      android_profiling_helper.sqlite3 = real_sqlite3


class TestAndroidProfilingHelperTabTestCase(tab_test_case.TabTestCase):

  def setUp(self):
    super(TestAndroidProfilingHelperTabTestCase, self).setUp()
    # pylint: disable=W0212
    browser_backend = self._browser._browser_backend
    self._device = browser_backend._adb.device()

  # Test fails: crbug.com/437081
  # @decorators.Enabled('android')
  @decorators.Disabled
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

      # Check that we have kernel symbols.
      assert os.path.exists(kallsyms)

      is_unstripped = re.compile(r'^/data/app/.*\.so$')
      has_unstripped = False

      # Check that all requested libraries are present.
      for lib in libs:
        has_unstripped = has_unstripped or is_unstripped.match(lib)
        assert os.path.exists(os.path.join(symfs_dir, lib[1:])), \
            '%s not found in symfs' % lib

      # Make sure we found at least one unstripped library.
      assert has_unstripped
    finally:
      shutil.rmtree(symfs_dir)

  # Test fails: crbug.com/437081
  # @decorators.Enabled('android')
  @decorators.Disabled
  def testGetToolchainBinaryPath(self):
    with tempfile.NamedTemporaryFile() as libc:
      self._device.PullFile('/system/lib/libc.so', libc.name)
      path = android_profiling_helper.GetToolchainBinaryPath(libc.name,
                                                             'objdump')
      assert os.path.exists(path)
