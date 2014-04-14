# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import signal
import subprocess
import sys
import tempfile

from telemetry.core import util
from telemetry.core.platform import profiler
from telemetry.core.platform.profiler import android_prebuilt_profiler_helper


class _SingleProcessPerfProfiler(object):
  """An internal class for using perf for a given process.

  On android, this profiler uses pre-built binaries from AOSP.
  See more details in prebuilt/android/README.txt.
  """
  def __init__(self, pid, output_file, browser_backend, platform_backend):
    self._pid = pid
    self._browser_backend = browser_backend
    self._platform_backend = platform_backend
    self._output_file = output_file
    self._tmp_output_file = tempfile.NamedTemporaryFile('w', 0)
    self._is_android = platform_backend.GetOSName() == 'android'
    cmd_prefix = []
    if self._is_android:
      perf_binary = android_prebuilt_profiler_helper.GetDevicePath(
          'perf')
      cmd_prefix = ['adb', '-s', browser_backend.adb.device(), 'shell',
                    perf_binary]
      output_file = os.path.join('/sdcard', 'perf_profiles',
                                 os.path.basename(output_file))
      self._device_output_file = output_file
      browser_backend.adb.RunShellCommand(
          'mkdir -p ' + os.path.dirname(self._device_output_file))
    else:
      cmd_prefix = ['perf']
    self._proc = subprocess.Popen(cmd_prefix +
        ['record', '--call-graph',
         '--pid', str(pid), '--output', output_file],
        stdout=self._tmp_output_file, stderr=subprocess.STDOUT)

  def CollectProfile(self):
    if ('renderer' in self._output_file and
        not self._is_android and
        not self._platform_backend.GetCommandLine(self._pid)):
      logging.warning('Renderer was swapped out during profiling. '
                      'To collect a full profile rerun with '
                      '"--extra-browser-args=--single-process"')
    if self._is_android:
      adb = self._browser_backend.adb.Adb()
      perf_pids = adb.ExtractPid('perf')
      adb.RunShellCommand('kill -SIGINT ' + ' '.join(perf_pids))
      util.WaitFor(lambda: not adb.ExtractPid('perf'), timeout=2)
    self._proc.send_signal(signal.SIGINT)
    exit_code = self._proc.wait()
    try:
      if exit_code == 128:
        raise Exception(
            """perf failed with exit code 128.
Try rerunning this script under sudo or setting
/proc/sys/kernel/perf_event_paranoid to "-1".\nOutput:\n%s""" %
            self._GetStdOut())
      elif exit_code not in (0, -2):
        raise Exception(
            'perf failed with exit code %d. Output:\n%s' % (exit_code,
                                                            self._GetStdOut()))
    finally:
      self._tmp_output_file.close()
    cmd = 'perf report -n -i %s' % self._output_file
    if self._is_android:
      print 'On Android, assuming $CHROMIUM_OUT_DIR/Release/lib has a fresh'
      print 'symbolized library matching the one on device.'
      objdump_path = os.path.join(os.environ.get('ANDROID_TOOLCHAIN',
                                                 '$ANDROID_TOOLCHAIN'),
                                  'arm-linux-androideabi-objdump')
      print 'If you have recent version of perf (3.10+), append the following '
      print 'to see annotated source code (by pressing the \'a\' key): '
      print '  --objdump %s' % objdump_path
      cmd += ' ' + ' '.join(self._PrepareAndroidSymfs())
    print 'To view the profile, run:'
    print ' ', cmd
    return self._output_file

  def _PrepareAndroidSymfs(self):
    """Create a symfs directory using an Android device.

    Create a symfs directory by pulling the necessary files from an Android
    device.

    Returns:
      List of arguments to be passed to perf to point it to the created symfs.
    """
    assert self._is_android
    adb = self._browser_backend.adb.Adb()
    adb.Adb().Pull(self._device_output_file, self._output_file)
    symfs_dir = os.path.dirname(self._output_file)
    host_app_symfs = os.path.join(symfs_dir, 'data', 'app-lib')
    if not os.path.exists(host_app_symfs):
      os.makedirs(host_app_symfs)
      # On Android, the --symfs parameter needs to map a directory structure
      # similar to the device, that is:
      # --symfs=/tmp/foobar and then inside foobar there'll be something like
      # /tmp/foobar/data/app-lib/$PACKAGE/libname.so
      # Assume the symbolized library under out/Release/lib is equivalent to
      # the one in the device, and symlink it in the host to match --symfs.
      device_dir = filter(
          lambda app_lib: app_lib.startswith(self._browser_backend.package),
          adb.RunShellCommand('ls /data/app-lib'))
      os.symlink(os.path.abspath(
                    os.path.join(util.GetChromiumSrcDir(),
                                 os.environ.get('CHROMIUM_OUT_DIR', 'out'),
                                 'Release', 'lib')),
                 os.path.join(host_app_symfs, device_dir[0]))

    # Also pull copies of common system libraries from the device so perf can
    # resolve their symbols. Only copy a subset of libraries to make this
    # faster.
    # TODO(skyostil): Find a way to pull in all system libraries without being
    # too slow.
    host_system_symfs = os.path.join(symfs_dir, 'system', 'lib')
    if not os.path.exists(host_system_symfs):
      os.makedirs(host_system_symfs)
      common_system_libs = [
        'libandroid*.so',
        'libart.so',
        'libc.so',
        'libdvm.so',
        'libEGL*.so',
        'libGL*.so',
        'libm.so',
        'libRS.so',
        'libskia.so',
        'libstdc++.so',
        'libstlport.so',
        'libz.so',
      ]
      for lib in common_system_libs:
        adb.Adb().Pull('/system/lib/%s' % lib, host_system_symfs)
    # Pull a copy of the kernel symbols.
    host_kallsyms = os.path.join(symfs_dir, 'kallsyms')
    if not os.path.exists(host_kallsyms):
      adb.Adb().Pull('/proc/kallsyms', host_kallsyms)
    return ['--kallsyms', host_kallsyms, '--symfs', symfs_dir]

  def _GetStdOut(self):
    self._tmp_output_file.flush()
    try:
      with open(self._tmp_output_file.name) as f:
        return f.read()
    except IOError:
      return ''


class PerfProfiler(profiler.Profiler):

  def __init__(self, browser_backend, platform_backend, output_path, state):
    super(PerfProfiler, self).__init__(
        browser_backend, platform_backend, output_path, state)
    process_output_file_map = self._GetProcessOutputFileMap()
    self._process_profilers = []
    if platform_backend.GetOSName() == 'android':
      android_prebuilt_profiler_helper.InstallOnDevice(
          browser_backend.adb.Adb(), 'perf')
      # Make sure kernel pointers are not hidden.
      browser_backend.adb.Adb().SetProtectedFileContents(
          '/proc/sys/kernel/kptr_restrict', '0')
    for pid, output_file in process_output_file_map.iteritems():
      if 'zygote' in output_file:
        continue
      self._process_profilers.append(
          _SingleProcessPerfProfiler(
              pid, output_file, browser_backend, platform_backend))

  @classmethod
  def name(cls):
    return 'perf'

  @classmethod
  def is_supported(cls, browser_type):
    if sys.platform != 'linux2':
      return False
    if browser_type.startswith('cros'):
      return False
    return cls._CheckLinuxPerf() or browser_type.startswith('android')

  @classmethod
  def _CheckLinuxPerf(cls):
    try:
      with open(os.devnull, 'w') as devnull:
        return not subprocess.Popen(['perf', '--version'],
                                    stderr=devnull,
                                    stdout=devnull).wait()
    except OSError:
      return False

  @classmethod
  def CustomizeBrowserOptions(cls, browser_type, options):
    options.AppendExtraBrowserArgs([
        '--no-sandbox',
        '--allow-sandbox-debugging',
    ])

  def CollectProfile(self):
    output_files = []
    for single_process in self._process_profilers:
      output_files.append(single_process.CollectProfile())
    return output_files

  @classmethod
  def GetTopSamples(cls, file_name, number):
    """Parses the perf generated profile in |file_name| and returns a
    {function: period} dict of the |number| hottests functions.
    """
    assert os.path.exists(file_name)
    with open(os.devnull, 'w') as devnull:
      report = subprocess.Popen(
          ['perf', 'report', '--show-total-period', '-U', '-t', '^', '-i',
           file_name],
          stdout=subprocess.PIPE, stderr=devnull).communicate()[0]
    period_by_function = {}
    for line in report.split('\n'):
      if not line or line.startswith('#'):
        continue
      fields = line.split('^')
      if len(fields) != 5:
        continue
      period = int(fields[1])
      function = fields[4].partition(' ')[2]
      function = re.sub('<.*>', '', function)  # Strip template params.
      function = re.sub('[(].*[)]', '', function)  # Strip function params.
      period_by_function[function] = period
      if len(period_by_function) == number:
        break
    return period_by_function
