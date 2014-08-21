# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import sysfs_platform


class AndroidSysfsPlatform(sysfs_platform.SysfsPlatform):
  """A SysfsPlatform implementation to be used for Android devices."""
  def __init__(self, device):
    """Constructor.

    Args:
        device: Android device to monitor.
    """
    super(AndroidSysfsPlatform, self).__init__()
    self._device = device

  def RunShellCommand(self, command):
    return '\n'.join(self._device.RunShellCommand(command))

  @staticmethod
  def ParseStateSample(sample):
    sample_stats = {}
    for cpu in sample:
      values = sample[cpu].splitlines()
      # Each state has three values after excluding the time value.
      num_states = (len(values) - 1) / 3
      names = values[:num_states]
      times = values[num_states:2 * num_states]
      cstates = {'C0': int(values[-1]) * 10 ** 6}
      for i, state in enumerate(names):
        if state == 'C0':
          # The Exynos cpuidle driver for the Nexus 10 uses the name 'C0' for
          # its WFI state.
          # TODO(tmandel): We should verify that no other Android device
          # actually reports time in C0 causing this to report active time as
          # idle time.
          state = 'WFI'
        cstates[state] = int(times[i])
        cstates['C0'] -= int(times[i])
      sample_stats[cpu] = cstates
    return sample_stats
