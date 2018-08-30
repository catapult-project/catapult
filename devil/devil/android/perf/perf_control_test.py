# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from devil import devil_env
from devil.android import device_utils
from devil.android.perf import perf_control
from devil.android.sdk import adb_wrapper

with devil_env.SysPath(devil_env.PYMOCK_PATH):
  import mock


# pylint: disable=unused-argument
def _ShellCommandHandler(cmd, shell=False, check_return=False,
    cwd=None, env=None, run_as=None, as_root=False, single_line=False,
    large_output=False, raw_output=False, timeout=None, retries=None):
  if cmd.startswith('for CPU in '):
    if 'scaling_available_governors' in cmd:
      contents = 'interactive ondemand userspace powersave performance'
      return [contents + '\n%~%0%~%'] * 4
    if 'cat "$CPU/online"' in cmd:
      return ['1\n%~%0%~%'] * 4
  assert False, 'Should not be called with cmd: {}'.format(cmd)


class PerfControlTest(unittest.TestCase):

  # pylint: disable=no-self-use
  def testNexus5HighPerfMode(self):
    # Mock out the device state for PerfControl.
    mock_device = mock.Mock(spec=device_utils.DeviceUtils)
    mock_device.product_model = 'Nexus 5'
    mock_device.adb = mock.Mock(spec=adb_wrapper.AdbWrapper)
    mock_device.ListDirectory.return_value = [
        'cpu%d' % cpu for cpu in xrange(4)] + ['cpufreq']
    mock_device.FileExists.return_value = True
    mock_device.RunShellCommand = mock.Mock(side_effect=_ShellCommandHandler)
    pc = perf_control.PerfControl(mock_device)

    # Set up mocks on PerfControl members when it is harder via mocking
    # RunShellCommand().
    # pylint: disable=protected-access
    pc.SetScalingGovernor = mock.Mock()
    pc._ForceAllCpusOnline = mock.Mock()
    pc._SetScalingMaxFreq = mock.Mock()
    pc._SetMaxGpuClock = mock.Mock()

    # Check the actions performed by SetHighPerfMode().
    pc.SetHighPerfMode()
    mock_device.EnableRoot.assert_called_once_with()
    pc._ForceAllCpusOnline.assert_called_once_with(True)
    pc.SetScalingGovernor.assert_called_once_with('performance')
    pc._SetScalingMaxFreq.assert_called_once_with(1190400)
    pc._SetMaxGpuClock.assert_called_once_with(200000000)
