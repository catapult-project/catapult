# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import benchmark
from telemetry.core.platform import android_device
from telemetry.core.platform import android_platform_backend
from telemetry.unittest import system_stub


class AndroidPlatformBackendTest(unittest.TestCase):
  def setUp(self):
    self._stubs = system_stub.Override(
        android_platform_backend,
        ['perf_control', 'thermal_throttle', 'adb_commands'])

  def tearDown(self):
    self._stubs.Restore()

  @benchmark.Disabled('chromeos')
  def testGetCpuStats(self):
    proc_stat_content = [
        '7702 (.android.chrome) S 167 167 0 0 -1 1077936448 '
        '3247 0 0 0 4 1 0 0 20 0 9 0 5603962 337379328 5867 '
        '4294967295 1074458624 1074463824 3197495984 3197494152 '
        '1074767676 0 4612 0 38136 4294967295 0 0 17 0 0 0 0 0 0 '
        '1074470376 1074470912 1102155776']
    self._stubs.adb_commands.adb_device.mock_content = proc_stat_content
    old_interface = self._stubs.adb_commands.adb_device.old_interface
    old_interface.can_access_protected_file_contents = True
    backend = android_platform_backend.AndroidPlatformBackend(
        android_device.AndroidDevice('12345'))
    cpu_stats = backend.GetCpuStats('7702')
    self.assertEquals(cpu_stats, {'CpuProcessTime': 5.0})

  @benchmark.Disabled('chromeos')
  def testGetCpuStatsInvalidPID(self):
    # Mock an empty /proc/pid/stat.
    backend = android_platform_backend.AndroidPlatformBackend(
        android_device.AndroidDevice('1234'))
    cpu_stats = backend.GetCpuStats('7702')
    self.assertEquals(cpu_stats, {})

  def testAndroidParseCpuStates(self):
    cstate = {
      'cpu0': 'C0\nC1\n103203424\n5342040\n300\n500\n1403232500',
      'cpu1': 'C0\n124361858\n300\n1403232500'
    }
    expected_cstate = {
      'cpu0': {
        'WFI': 103203424,
        'C0': 1403232391454536,
        'C1': 5342040
      },
      'cpu1': {
        'WFI': 124361858,
        'C0': 1403232375638142
      }
    }
    # Use mock start and end times to allow for the test to calculate C0.
    result = android_platform_backend.AndroidPlatformBackend.ParseCStateSample(
        cstate)
    for cpu in result:
      for state in result[cpu]:
        self.assertAlmostEqual(result[cpu][state], expected_cstate[cpu][state])
