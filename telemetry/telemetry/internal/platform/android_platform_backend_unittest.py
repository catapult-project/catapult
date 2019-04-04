# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators
from telemetry.core import util
from telemetry.internal.platform import android_device
from telemetry.internal.platform import android_platform_backend
from telemetry.testing import system_stub
import mock

from devil.android import battery_utils
from devil.android import device_utils

class AndroidPlatformBackendTest(unittest.TestCase):
  def setUp(self):
    self._stubs = system_stub.Override(
        android_platform_backend,
        ['perf_control', 'thermal_throttle'])

    self.fix_adb_instability_patcher = mock.patch.object(
        android_platform_backend, '_FixPossibleAdbInstability')
    self.fix_adb_instability_patcher.start()

    self.battery_patcher = mock.patch.object(battery_utils, 'BatteryUtils')
    self.battery_patcher.start()

    def get_prop(name, cache=None):
      del cache  # unused
      return {'ro.product.cpu.abi': 'armeabi-v7a'}.get(name)

    self.device_patcher = mock.patch.multiple(
        device_utils.DeviceUtils,
        HasRoot=mock.MagicMock(return_value=True),
        GetProp=mock.MagicMock(side_effect=get_prop))
    self.device_patcher.start()

  def tearDown(self):
    self._stubs.Restore()
    self.fix_adb_instability_patcher.stop()
    self.battery_patcher.stop()
    self.device_patcher.stop()

  @staticmethod
  def CreatePlatformBackendForTest():
    return android_platform_backend.AndroidPlatformBackend(
        android_device.AndroidDevice('12345'))

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsSvelte(self):
    with mock.patch('devil.android.device_utils.DeviceUtils.GetProp',
                    return_value='svelte'):
      backend = self.CreatePlatformBackendForTest()
      self.assertTrue(backend.IsSvelte())

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsNotSvelte(self):
    with mock.patch('devil.android.device_utils.DeviceUtils.GetProp',
                    return_value='foo'):
      backend = self.CreatePlatformBackendForTest()
      self.assertFalse(backend.IsSvelte())

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsAosp(self):
    with mock.patch('devil.android.device_utils.DeviceUtils.GetProp',
                    return_value='aosp'):
      backend = self.CreatePlatformBackendForTest()
      self.assertTrue(backend.IsAosp())

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsNotAosp(self):
    with mock.patch('devil.android.device_utils.DeviceUtils.GetProp',
                    return_value='foo'):
      backend = self.CreatePlatformBackendForTest()
      self.assertFalse(backend.IsAosp())

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testGetCpuStats(self):
    proc_stat_content = (
        '7702 (.android.chrome) S 167 167 0 0 -1 1077936448 '
        '3247 0 0 0 4 1 0 0 20 0 9 0 5603962 337379328 5867 '
        '4294967295 1074458624 1074463824 3197495984 3197494152 '
        '1074767676 0 4612 0 38136 4294967295 0 0 17 0 0 0 0 0 0 '
        '1074470376 1074470912 1102155776\n')
    with mock.patch('devil.android.device_utils.DeviceUtils.ReadFile',
                    return_value=proc_stat_content):
      backend = self.CreatePlatformBackendForTest()
      cpu_stats = backend.GetCpuStats('7702')
      self.assertEquals(cpu_stats, {'CpuProcessTime': 0.05})

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testGetCpuStatsInvalidPID(self):
    # Mock an empty /proc/pid/stat.
    with mock.patch('devil.android.device_utils.DeviceUtils.ReadFile',
                    return_value=''):
      backend = self.CreatePlatformBackendForTest()
      cpu_stats = backend.GetCpuStats('7702')
      self.assertEquals(cpu_stats, {})

  @decorators.Disabled('chromeos', 'mac', 'win')
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

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsScreenLockedTrue(self):
    test_input = ['a=b', 'mHasBeenInactive=true']
    backend = self.CreatePlatformBackendForTest()
    self.assertTrue(backend._IsScreenLocked(test_input))

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testIsScreenLockedFalse(self):
    test_input = ['a=b', 'mHasBeenInactive=false']
    backend = self.CreatePlatformBackendForTest()
    self.assertFalse(backend._IsScreenLocked(test_input))

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPackageExtractionNotFound(self):
    backend = self.CreatePlatformBackendForTest()
    self.assertEquals(
        'com.google.android.apps.chrome',
        backend._ExtractLastNativeCrashPackageFromLogcat('no crash info here'))

  @staticmethod
  def GetExampleLogcat():
    test_file = os.path.join(util.GetUnittestDataDir(), 'crash_in_logcat.txt')
    with open(test_file) as f:
      return f.read()

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPackageExtractionFromRealExample(self):
    backend = self.CreatePlatformBackendForTest()
    self.assertEquals('com.google.android.apps.chrome',
                      backend._ExtractLastNativeCrashPackageFromLogcat(
                          self.GetExampleLogcat(),
                          default_package_name='invalid'))

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPackageExtractionWithProcessName(self):
    backend = self.CreatePlatformBackendForTest()
    test_file = os.path.join(util.GetUnittestDataDir(),
                             'crash_in_logcat_with_process_name.txt')
    with open(test_file) as f:
      logcat = f.read()
    self.assertEquals(
        "org.chromium.chrome",
        backend._ExtractLastNativeCrashPackageFromLogcat(logcat))

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPackageExtractionWithTwoCrashes(self):
    """Check that among two matches the latest package name is taken."""
    backend = self.CreatePlatformBackendForTest()
    original_logcat = self.GetExampleLogcat()
    mutated_logcat = original_logcat.replace('com.google.android.apps.chrome',
                                             'com.android.chrome')
    concatenated_logcat = '\n'.join([original_logcat, mutated_logcat])
    self.assertEquals(
        'com.android.chrome',
        backend._ExtractLastNativeCrashPackageFromLogcat(concatenated_logcat))


class AndroidPlatformBackendPsutilTest(unittest.TestCase):

  class psutil_1_0(object):
    version_info = (1, 0)
    def __init__(self):
      self.set_cpu_affinity_args = []
    class Process(object):
      def __init__(self, parent):
        self._parent = parent
        self.name = 'adb'
      def set_cpu_affinity(self, cpus):
        self._parent.set_cpu_affinity_args.append(cpus)
    def process_iter(self):
      return [self.Process(self)]

  class psutil_2_0(object):
    version_info = (2, 0)
    def __init__(self):
      self.set_cpu_affinity_args = []
    class Process(object):
      def __init__(self, parent):
        self._parent = parent
        self.set_cpu_affinity_args = []
      def name(self):
        return 'adb'
      def cpu_affinity(self, cpus=None):
        self._parent.set_cpu_affinity_args.append(cpus)
    def process_iter(self):
      return [self.Process(self)]

  def setUp(self):
    self._stubs = system_stub.Override(
        android_platform_backend,
        ['perf_control'])
    self.battery_patcher = mock.patch.object(battery_utils, 'BatteryUtils')
    self.battery_patcher.start()

    def get_prop(name, cache=None):
      del cache  # unused
      return {'ro.product.cpu.abi': 'armeabi-v7a'}.get(name)

    self.device_patcher = mock.patch.multiple(
        device_utils.DeviceUtils,
        FileExists=mock.MagicMock(return_value=False),
        GetProp=mock.MagicMock(side_effect=get_prop),
        HasRoot=mock.MagicMock(return_value=True))
    self.device_patcher.start()

  def tearDown(self):
    self._stubs.Restore()
    self.battery_patcher.stop()
    self.device_patcher.stop()

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPsutil1(self):
    with mock.patch.object(
        android_platform_backend, 'psutil', self.psutil_1_0()) as psutil:
      # Mock an empty /proc/pid/stat.
      with mock.patch('devil.android.device_utils.DeviceUtils.ReadFile',
                      return_value=''):
        backend = android_platform_backend.AndroidPlatformBackend(
            android_device.AndroidDevice('1234'))
        cpu_stats = backend.GetCpuStats('7702')
        self.assertEquals({}, cpu_stats)
        self.assertEquals([[0]], psutil.set_cpu_affinity_args)

  @decorators.Disabled('chromeos', 'mac', 'win')
  def testPsutil2(self):
    with mock.patch.object(
        android_platform_backend, 'psutil', self.psutil_2_0()) as psutil:
      # Mock an empty /proc/pid/stat.
      with mock.patch('devil.android.device_utils.DeviceUtils.ReadFile',
                      return_value=''):
        backend = android_platform_backend.AndroidPlatformBackend(
            android_device.AndroidDevice('1234'))
        cpu_stats = backend.GetCpuStats('7702')
        self.assertEquals({}, cpu_stats)
        self.assertEquals([[0]], psutil.set_cpu_affinity_args)
