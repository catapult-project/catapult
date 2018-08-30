# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import atexit
import logging
import re

from devil.android import device_errors

logger = logging.getLogger(__name__)
_atexit_messages = set()


# Defines how to switch between the default performance configuration
# ('default_mode') and the mode for use when benchmarking ('high_perf_mode').
# For devices not in the list the defaults are to set up the scaling governor to
# 'performance' and reset it back to 'ondemand' when benchmarking is finished.
#
# The 'default_mode_governor' is mandatory to define, while
# 'high_perf_mode_governor' is not taken into account. The latter is because the
# governor 'performance' is currently used for all benchmarking on all devices.
#
# TODO(crbug.com/383566): Add definitions for all devices used in the perf
# waterfall.
_PERFORMANCE_MODE_DEFINITIONS = {
  'GT-I9300': {
    'default_mode_governor': 'pegasusq',
  },
  'Galaxy Nexus': {
    'default_mode_governor': 'interactive',
  },
  'Nexus 7': {
    'default_mode_governor': 'interactive',
  },
  'Nexus 10': {
    'default_mode_governor': 'interactive',
  },
  'Nexus 4': {
    'high_perf_mode': {
      'bring_cpu_cores_online': True,
    },
    'default_mode_governor': 'ondemand',
  },
  'Nexus 5': {
    # The list of possible GPU frequency values can be found in:
    #     /sys/class/kgsl/kgsl-3d0/gpu_available_frequencies.
    # For CPU cores the possible frequency values are at:
    #     /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
    'high_perf_mode': {
      'bring_cpu_cores_online': True,
      'cpu_max_freq': 1190400,
      'gpu_max_freq': 200000000,
    },
    'default_mode': {
      'cpu_max_freq': 2265600,
      'gpu_max_freq': 450000000,
    },
    'default_mode_governor': 'ondemand',
  },
}


def _NoisyWarning(message):
  message += ' Results may be NOISY!!'
  logger.warning(message)
  # Add an additional warning at exit, such that it's clear that any results
  # may be different/noisy (due to the lack of intended performance mode).
  if message not in _atexit_messages:
    _atexit_messages.add(message)
    atexit.register(logger.warning, message)


class PerfControl(object):
  """Provides methods for setting the performance mode of a device."""

  _AVAILABLE_GOVERNORS_REL_PATH = 'cpufreq/scaling_available_governors'
  _CPU_FILE_PATTERN = re.compile(r'^cpu\d+$')
  _CPU_PATH = '/sys/devices/system/cpu'
  _KERNEL_MAX = '/sys/devices/system/cpu/kernel_max'

  def __init__(self, device):
    self._device = device
    self._cpu_files = []
    for file_name in self._device.ListDirectory(self._CPU_PATH, as_root=True):
      if self._CPU_FILE_PATTERN.match(file_name):
        self._cpu_files.append(file_name)
    assert self._cpu_files, 'Failed to detect CPUs.'
    self._cpu_file_list = ' '.join(self._cpu_files)
    logger.info('CPUs found: %s', self._cpu_file_list)

    self._have_mpdecision = self._device.FileExists('/system/bin/mpdecision')

    raw = self._ReadEachCpuFile(self._AVAILABLE_GOVERNORS_REL_PATH)
    self._available_governors = [
        (cpu, raw_governors.strip().split() if not exit_code else None)
        for cpu, raw_governors, exit_code in raw]

  def _SetMaxFrequenciesFromMode(self, mode):
    """Set maximum frequencies for GPU and CPU cores.

    Args:
      mode: A dictionary mapping optional keys 'cpu_max_freq' and 'gpu_max_freq'
            to integer values of frequency supported by the device.
    """
    cpu_max_freq = mode.get('cpu_max_freq')
    if cpu_max_freq:
      self._SetScalingMaxFreq(cpu_max_freq)
    gpu_max_freq = mode.get('gpu_max_freq')
    if gpu_max_freq:
      self._SetMaxGpuClock(gpu_max_freq)

  def SetHighPerfMode(self):
    """Sets the highest stable performance mode for the device."""
    try:
      self._device.EnableRoot()
    except device_errors.CommandFailedError:
      _NoisyWarning('Need root for performance mode.')
      return
    mode_definitions = _PERFORMANCE_MODE_DEFINITIONS.get(
        self._device.product_model)
    if not mode_definitions:
      self.SetScalingGovernor('performance')
      return
    high_perf_mode = mode_definitions.get('high_perf_mode')
    if not high_perf_mode:
      self.SetScalingGovernor('performance')
      return
    if high_perf_mode.get('bring_cpu_cores_online', False):
      self._ForceAllCpusOnline(True)
      if not self._AllCpusAreOnline():
        _NoisyWarning('Failed to force CPUs online.')
    # Scaling governor must be set _after_ bringing all CPU cores online,
    # otherwise it would not affect the cores that are currently offline.
    self.SetScalingGovernor('performance')
    self._SetMaxFrequenciesFromMode(high_perf_mode)

  def SetDefaultPerfMode(self):
    """Sets the performance mode for the device to its default mode."""
    if not self._device.HasRoot():
      return
    mode_definitions = _PERFORMANCE_MODE_DEFINITIONS.get(
        self._device.product_model)
    if not mode_definitions:
      self.SetScalingGovernor('ondemand')
    else:
      default_mode_governor = mode_definitions.get('default_mode_governor')
      assert default_mode_governor, ('Default mode governor must be provided '
          'for all perf mode definitions.')
      self.SetScalingGovernor(default_mode_governor)
      default_mode = mode_definitions.get('default_mode')
      if default_mode:
        self._SetMaxFrequenciesFromMode(default_mode)
    self._ForceAllCpusOnline(False)

  def SetPerfProfilingMode(self):
    """Enables all cores for reliable perf profiling."""
    self._ForceAllCpusOnline(True)
    self.SetScalingGovernor('performance')
    if not self._AllCpusAreOnline():
      if not self._device.HasRoot():
        raise RuntimeError('Need root to force CPUs online.')
      raise RuntimeError('Failed to force CPUs online.')

  def GetCpuInfo(self):
    online = (output.rstrip() == '1' and status == 0
              for (_, output, status) in self._ForEachCpu('cat "$CPU/online"'))
    governor = (output.rstrip() if status == 0 else None
                for (_, output, status)
                in self._ForEachCpu('cat "$CPU/cpufreq/scaling_governor"'))
    return zip(self._cpu_files, online, governor)

  def _ForEachCpu(self, cmd):
    """Runs a command on the device for each of the CPUs on it.

    Args:
      cmd: A string with a shell command, may may use shell expansion: "$CPU" to
           refer to the current CPU in the string form (e.g. "cpu0", "cpu1",
           and so on).
    Returns:
      A list of tuples in the form (cpu_string, command_output, exit_code), one
      tuple per each command invocation. As usual, all lines of the output
      command are joined into one line with spaces.
    """
    script = '; '.join([
        'for CPU in %s' % self._cpu_file_list,
        'do %s' % cmd,
        'echo -n "%~%$?%~%"',
        'done'
    ])
    output = self._device.RunShellCommand(
        script, cwd=self._CPU_PATH, check_return=True, as_root=True, shell=True)
    output = '\n'.join(output).split('%~%')
    return zip(self._cpu_files, output[0::2], (int(c) for c in output[1::2]))

  def _WriteEachCpuFile(self, path, value):
    self._ConditionallyWriteEachCpuFile(path, value, condition='true')

  def _ConditionallyWriteEachCpuFile(self, path, value, condition):
    template = (
        '{condition} && test -e "$CPU/{path}" && echo {value} > "$CPU/{path}"')
    results = self._ForEachCpu(
        template.format(path=path, value=value, condition=condition))
    cpus = ' '.join(cpu for (cpu, _, status) in results if status == 0)
    if cpus:
      logger.info('Successfully set %s to %r on: %s', path, value, cpus)
    else:
      logger.warning('Failed to set %s to %r on any cpus', path, value)

  def _ReadEachCpuFile(self, path):
    return self._ForEachCpu(
        'cat "$CPU/{path}"'.format(path=path))

  def SetScalingGovernor(self, value):
    """Sets the scaling governor to the given value on all possible CPUs.

    This does not attempt to set a governor to a value not reported as available
    on the corresponding CPU.

    Args:
      value: [string] The new governor value.
    """
    condition = 'test -e "{path}" && grep -q {value} {path}'.format(
        path=('${CPU}/%s' % self._AVAILABLE_GOVERNORS_REL_PATH),
        value=value)
    self._ConditionallyWriteEachCpuFile(
        'cpufreq/scaling_governor', value, condition)

  def GetScalingGovernor(self):
    """Gets the currently set governor for each CPU.

    Returns:
      An iterable of 2-tuples, each containing the cpu and the current
      governor.
    """
    raw = self._ReadEachCpuFile('cpufreq/scaling_governor')
    return [
        (cpu, raw_governor.strip() if not exit_code else None)
        for cpu, raw_governor, exit_code in raw]

  def ListAvailableGovernors(self):
    """Returns the list of available governors for each CPU.

    Returns:
      An iterable of 2-tuples, each containing the cpu and a list of available
      governors for that cpu.
    """
    return self._available_governors

  def _SetScalingMaxFreq(self, value):
    self._WriteEachCpuFile('cpufreq/scaling_max_freq', '%d' % value)

  def _SetMaxGpuClock(self, value):
    self._device.WriteFile('/sys/class/kgsl/kgsl-3d0/max_gpuclk',
                           str(value),
                           as_root=True)

  def _AllCpusAreOnline(self):
    results = self._ForEachCpu('cat "$CPU/online"')
    # The file 'cpu0/online' is missing on some devices (example: Nexus 9). This
    # is likely because on these devices it is impossible to bring the cpu0
    # offline. Assuming the same for all devices until proven otherwise.
    return all(output.rstrip() == '1' and status == 0
               for (cpu, output, status) in results
               if cpu != 'cpu0')

  def _ForceAllCpusOnline(self, force_online):
    """Enable all CPUs on a device.

    Some vendors (or only Qualcomm?) hot-plug their CPUs, which can add noise
    to measurements:
    - In perf, samples are only taken for the CPUs that are online when the
      measurement is started.
    - The scaling governor can't be set for an offline CPU and frequency scaling
      on newly enabled CPUs adds noise to both perf and tracing measurements.

    It appears Qualcomm is the only vendor that hot-plugs CPUs, and on Qualcomm
    this is done by "mpdecision".

    """
    if self._have_mpdecision:
      cmd = ['stop', 'mpdecision'] if force_online else ['start', 'mpdecision']
      self._device.RunShellCommand(cmd, check_return=True, as_root=True)

    if not self._have_mpdecision and not self._AllCpusAreOnline():
      logger.warning('Unexpected cpu hot plugging detected.')

    if force_online:
      self._ForEachCpu('echo 1 > "$CPU/online"')
