# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import cros_device
from telemetry.core.platform import cros_interface
from telemetry.core.platform import linux_based_platform_backend
from telemetry.core.platform import ps_util
from telemetry.core.platform.power_monitor import cros_power_monitor


class CrosPlatformBackend(
    linux_based_platform_backend.LinuxBasedPlatformBackend):

  def __init__(self, device=None):
    super(CrosPlatformBackend, self).__init__(device)
    if device:
      self._cri = cros_interface.CrOSInterface(
          device.host_name, device.ssh_identity)
      self._cri.TryLogin()
    else:
      self._cri = cros_interface.CrOSInterface()
    self._powermonitor = cros_power_monitor.CrosPowerMonitor(self)

  @classmethod
  def SupportsDevice(cls, device):
    return isinstance(device, cros_device.CrOSDevice)

  @property
  def cri(self):
    return self._cri

  def StartRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def GetRawDisplayFrameRateMeasurements(self):
    raise NotImplementedError()

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def RunCommand(self, args):
    return self._cri.RunCmdOnDevice(args)[0]

  def GetFileContents(self, filename):
    try:
      return self.RunCommand(['cat', filename])
    except AssertionError:
      return ''

  @staticmethod
  def ParseCStateSample(sample):
    sample_stats = {}
    for cpu in sample:
      values = sample[cpu].splitlines()
      # There are three values per state after excluding the single time value.
      num_states = (len(values) - 1) / 3
      names = values[:num_states]
      times = values[num_states:2 * num_states]
      latencies = values[2 * num_states:]
      # The last line in the sample contains the time.
      cstates = {'C0': int(values[-1]) * 10 ** 6}
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

  def GetIOStats(self, pid):
    # There is no '/proc/<pid>/io' file on CrOS platforms
    # Returns empty dict as it does in PlatformBackend.
    return {}

  def GetOSName(self):
    return 'chromeos'

  def GetOSVersionName(self):
    return ''  # TODO: Implement this.

  def GetChildPids(self, pid):
    """Returns a list of child pids of |pid|."""
    all_process_info = self._cri.ListProcesses()
    processes = [(curr_pid, curr_ppid, curr_state)
                 for curr_pid, _, curr_ppid, curr_state in all_process_info]
    return ps_util.GetChildPids(processes, pid)

  def GetCommandLine(self, pid):
    procs = self._cri.ListProcesses()
    return next((proc[1] for proc in procs if proc[0] == pid), None)

  def CanFlushIndividualFilesFromSystemCache(self):
    return True

  def FlushEntireSystemCache(self):
    raise NotImplementedError()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def CanMonitorPower(self):
    return self._powermonitor.CanMonitorPower()

  def StartMonitoringPower(self, browser):
    self._powermonitor.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    return self._powermonitor.StopMonitoringPower()
