# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform.power_monitor import sysfs_platform


class CrosSysfsPlatform(sysfs_platform.SysfsPlatform):
  """A SysfsPlatform implementation to be used for ChromeOS devices."""
  def __init__(self, cri):
    """Constructor.

    Args:
        cri: Chrome interface.
    """
    super(CrosSysfsPlatform, self).__init__()
    self._cri = cri

  def RunShellCommand(self, command):
    return self._cri.RunCmdOnDevice(command.split())[0]

  @staticmethod
  def ParseStateSample(sample, time):
    sample_stats = {}
    for cpu in sample:
      cstates = {'C0': time * 10 ** 6}
      values = sample[cpu].splitlines()
      num_states = len(values) / 3
      names = values[:num_states]
      times = values[num_states:2 * num_states]
      latencies = values[2 * num_states:]
      for i, state in enumerate(names):
        if names[i] == 'POLL' and not int(latencies[i]):
          # C0 state. Kernel stats aren't right, so calculate by
          # subtracting all other states from total time (using epoch
          # timer since we calculate differences in the end anyway).
          # NOTE: Only x86 lists C0 under cpuidle, ARM does not.
          continue
        cstates['C0'] -= int(times[i])
        if names[i] == '<null>':
          # Kernel race condition that can happen while a new C-state gets
          # added (e.g. AC->battery). Don't know the 'name' of the state
          # yet, but its 'time' would be 0 anyway.
          continue
        cstates[state] = int(times[i])
      sample_stats[cpu] = cstates
    return sample_stats
