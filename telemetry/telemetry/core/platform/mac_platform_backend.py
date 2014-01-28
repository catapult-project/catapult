# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import ctypes
import logging
import os
import plistlib
import signal
import subprocess
import tempfile
import time
try:
  import resource  # pylint: disable=F0401
except ImportError:
  resource = None  # Not available on all platforms

from ctypes import util
from telemetry.core.platform import posix_platform_backend

class MacPlatformBackend(posix_platform_backend.PosixPlatformBackend):

  class PowerMetricsUtility(object):
    def __init__(self):
      self._powermetrics_process = None
      self._powermetrics_output_file = None

    @property
    def binary_path(self):
      return '/usr/bin/powermetrics'

    def StartMonitoringPowerAsync(self):
      assert not self._powermetrics_process, (
          "Must call StopMonitoringPowerAsync().")
      SAMPLE_INTERVAL_MS = 1000 / 20 # 20 Hz, arbitrary.
      self._powermetrics_output_file = tempfile.NamedTemporaryFile()
      args = [self.binary_path, '-f', 'plist', '-i',
          '%d' % SAMPLE_INTERVAL_MS, '-u', self._powermetrics_output_file.name]

      # powermetrics writes lots of output to stderr, don't echo unless verbose
      # logging enabled.
      stderror_destination = subprocess.PIPE
      if logging.getLogger().isEnabledFor(logging.DEBUG):
        stderror_destination = None

      self._powermetrics_process = subprocess.Popen(args,
          stdout=subprocess.PIPE, stderr=stderror_destination)

    def StopMonitoringPowerAsync(self):
      assert self._powermetrics_process, (
          "StartMonitoringPowerAsync() not called.")
      # Tell powermetrics to take an immediate sample.
      try:
        self._powermetrics_process.send_signal(signal.SIGINFO)
        self._powermetrics_process.send_signal(signal.SIGTERM)
        returncode = self._powermetrics_process.wait()
        assert returncode in [0, -15], (
            "powermetrics return code: %d" % returncode)
        return open(self._powermetrics_output_file.name, 'r').read()
      finally:
        self._powermetrics_output_file.close()
        self._powermetrics_output_file = None
        self._powermetrics_process = None

  def __init__(self):
    super(MacPlatformBackend, self).__init__()
    self.libproc = None
    self.powermetrics_tool_ = MacPlatformBackend.PowerMetricsUtility()

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

  def GetCpuStats(self, pid):
    """Return current cpu processing time of pid in seconds."""
    class ProcTaskInfo(ctypes.Structure):
      """Struct for proc_pidinfo() call."""
      _fields_ = [("pti_virtual_size", ctypes.c_uint64),
                  ("pti_resident_size", ctypes.c_uint64),
                  ("pti_total_user", ctypes.c_uint64),
                  ("pti_total_system", ctypes.c_uint64),
                  ("pti_threads_user", ctypes.c_uint64),
                  ("pti_threads_system", ctypes.c_uint64),
                  ("pti_policy", ctypes.c_int32),
                  ("pti_faults", ctypes.c_int32),
                  ("pti_pageins", ctypes.c_int32),
                  ("pti_cow_faults", ctypes.c_int32),
                  ("pti_messages_sent", ctypes.c_int32),
                  ("pti_messages_received", ctypes.c_int32),
                  ("pti_syscalls_mach", ctypes.c_int32),
                  ("pti_syscalls_unix", ctypes.c_int32),
                  ("pti_csw", ctypes.c_int32),
                  ("pti_threadnum", ctypes.c_int32),
                  ("pti_numrunning", ctypes.c_int32),
                  ("pti_priority", ctypes.c_int32)]
      PROC_PIDTASKINFO = 4
      def __init__(self):
        self.size = ctypes.sizeof(self)
        super(ProcTaskInfo, self).__init__()

    proc_info = ProcTaskInfo()
    if not self.libproc:
      self.libproc = ctypes.CDLL(util.find_library('libproc'))
    self.libproc.proc_pidinfo(pid, proc_info.PROC_PIDTASKINFO, 0,
                              ctypes.byref(proc_info), proc_info.size)

    # Convert nanoseconds to seconds
    cpu_time = (proc_info.pti_total_user / 1000000000.0 +
                proc_info.pti_total_system / 1000000000.0)
    return {'CpuProcessTime': cpu_time}

  def GetCpuTimestamp(self):
    """Return current timestamp in seconds."""
    return {'TotalTime': time.time()}

  def GetSystemCommitCharge(self):
    vm_stat = self._RunCommand(['vm_stat'])
    for stat in vm_stat.splitlines():
      key, value = stat.split(':')
      if key == 'Pages active':
        pages_active = int(value.strip()[:-1])  # Strip trailing '.'
        return pages_active * resource.getpagesize() / 1024
    return 0

  def PurgeUnpinnedMemory(self):
    # TODO(pliard): Implement this.
    pass

  def GetMemoryStats(self, pid):
    rss_vsz = self._GetPsOutput(['rss', 'vsz'], pid)
    if rss_vsz:
      rss, vsz = rss_vsz[0].split()
      return {'VM': 1024 * int(vsz),
              'WorkingSetSize': 1024 * int(rss)}
    return {}

  def GetOSName(self):
    return 'mac'

  def GetOSVersionName(self):
    os_version = os.uname()[2]

    if os_version.startswith('9.'):
      return 'leopard'
    if os_version.startswith('10.'):
      return 'snowleopard'
    if os_version.startswith('11.'):
      return 'lion'
    if os_version.startswith('12.'):
      return 'mountainlion'
    if os_version.startswith('13.'):
      return 'mavericks'

    raise NotImplementedError("Unknown OS X version %s." % os_version)

  def CanFlushIndividualFilesFromSystemCache(self):
    return False

  def FlushEntireSystemCache(self):
    p = subprocess.Popen(['purge'])
    p.wait()
    assert p.returncode == 0, 'Failed to flush system cache'

  def CanMonitorPowerAsync(self):
    # powermetrics only runs on OS X version >= 10.9 .
    os_version = int(os.uname()[2].split('.')[0])
    binary_path = self.powermetrics_tool_.binary_path
    return os_version >= 13 and self.CanLaunchApplication(binary_path)

  def SetPowerMetricsUtilityForTest(self, obj):
    self.powermetrics_tool_ = obj

  def StartMonitoringPowerAsync(self):
    self.powermetrics_tool_.StartMonitoringPowerAsync()

  def _ParsePowerMetricsOutput(self, powermetrics_output):
    """Parse output of powermetrics command line utility.

    Returns:
        Dictionary in the format returned by StopMonitoringPowerAsync().
    """

    # Container to collect samples for running averages.
    # out_path - list containing the key path in the output dictionary.
    # src_path - list containing the key path to get the data from in
    #    powermetrics' output.
    def ConstructMetric(out_path, src_path):
      RunningAverage = collections.namedtuple('RunningAverage', [
        'out_path', 'src_path', 'samples'])
      return RunningAverage(out_path, src_path, [])

    # List of RunningAverage objects specifying metrics we want to aggregate.
    metrics = [
        ConstructMetric(
            ['component_utilization', 'whole_package', 'average_frequency_mhz'],
            ['processor','freq_hz']),
        ConstructMetric(
            ['component_utilization', 'whole_package', 'idle_percent'],
            ['processor','packages', 0, 'c_state_ratio'])]

    def DataWithMetricKeyPath(metric, powermetrics_output):
      """Retrieve the sample from powermetrics' output for a given metric.

      Args:
          metric: The RunningAverage object we want to collect a new sample for.
          powermetrics_output: Dictionary containing powermetrics output.

      Returns:
          The sample corresponding to |metric|'s keypath."""
      # Get actual data corresponding to key path.
      out_data = powermetrics_output
      for k in metric.src_path:
        out_data = out_data[k]

      assert type(out_data) in [int, float], (
          "Was expecting a number: %s (%s)" % (type(out_data), out_data))
      return float(out_data)

    power_samples = []
    sample_durations = []
    total_energy_consumption_mwh = 0
    # powermetrics outputs multiple plists separated by null terminators.
    raw_plists = powermetrics_output.split('\0')
    raw_plists = [x for x in raw_plists if len(x) > 0]

    # -------- Examine contents of first plist for systems specs. --------
    plist = plistlib.readPlistFromString(raw_plists[0])

    if 'GPU' in plist:
      metrics.extend([
          ConstructMetric(
              ['component_utilization', 'gpu', 'average_frequency_mhz'],
              ['GPU', 0, 'freq_hz']),
          ConstructMetric(
              ['component_utilization', 'gpu', 'idle_percent'],
              ['GPU', 0, 'c_state_ratio'])])


    # There's no way of knowing ahead of time how many cpus and packages the
    # current system has. Iterate over cores and cpus - construct metrics for
    # each one.
    if 'processor' in plist:
      core_dict = plist['processor']['packages'][0]['cores']
      num_cores = len(core_dict)
      cpu_num = 0
      for core_idx in xrange(num_cores):
        num_cpus = len(core_dict[core_idx]['cpus'])
        base_src_path = ['processor', 'packages', 0, 'cores', core_idx]
        for cpu_idx in xrange(num_cpus):
          base_out_path = ['component_utilization', 'cpu%d' % cpu_num]
          # C State ratio is per-package, component CPUs of that package may
          # have different frequencies.
          metrics.append(ConstructMetric(
              base_out_path + ['average_frequency_mhz'],
              base_src_path + ['cpus', cpu_idx, 'freq_hz']))
          metrics.append(ConstructMetric(
              base_out_path + ['idle_percent'],
              base_src_path + ['c_state_ratio']))
          cpu_num += 1

    # -------- Parse Data Out of Plists --------
    for raw_plist in raw_plists:
      plist = plistlib.readPlistFromString(raw_plist)

      # Duration of this sample.
      sample_duration_ms = int(plist['elapsed_ns']) / 10**6
      sample_durations.append(sample_duration_ms)

      if 'processor' not in plist:
        continue
      processor = plist['processor']

      energy_consumption_mw = int(processor.get('package_watts', 0)) * 10**3

      total_energy_consumption_mwh += (energy_consumption_mw *
          (sample_duration_ms / 3600000.))

      power_samples.append(energy_consumption_mw)

      for m in metrics:
        m.samples.append(DataWithMetricKeyPath(m, plist))

    # -------- Collect and Process Data --------
    out_dict = {}
    # Raw power usage samples.
    if power_samples:
      out_dict['power_samples_mw'] = power_samples
      out_dict['energy_consumption_mwh'] = total_energy_consumption_mwh

    def StoreMetricAverage(metric, sample_durations, out):
      """Calculate average value of samples in a metric and store in output
         path as specified by metric.

      Args:
          metric: A RunningAverage object containing samples to average.
          sample_durations: A list which parallels the samples list containing
              the time slice for each sample.
          out: The output dicat, average is stored in the location specified by
              metric.out_path.
      """
      if len(metric.samples) == 0:
        return

      assert len(metric.samples) == len(sample_durations)
      avg = 0
      for i in xrange(len(metric.samples)):
        avg += metric.samples[i] * sample_durations[i]
      avg /= sum(sample_durations)

      # Store data in output, creating empty dictionaries as we go.
      for k in metric.out_path[:-1]:
        if not out.has_key(k):
          out[k] = {}
        out = out[k]
      out[metric.out_path[-1]] = avg

    for m in metrics:
      StoreMetricAverage(m, sample_durations, out_dict)
    return out_dict

  def StopMonitoringPowerAsync(self):
    powermetrics_output = self.powermetrics_tool_.StopMonitoringPowerAsync()
    assert len(powermetrics_output) > 0
    return self._ParsePowerMetricsOutput(powermetrics_output)
