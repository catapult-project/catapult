# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(yzshen): Once the dep manager is ready, remove this file and use the one
# from src/mojo/tools directly.


import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from .paths import Paths

from devil import base_error
from devil.android import apk_helper
from devil.android import device_errors
from devil.android import device_utils
from pylib import constants


# Tags used by the mojo shell application logs.
LOGCAT_TAGS = [
    'AndroidHandler',
    'MojoFileHelper',
    'MojoMain',
    'MojoShellActivity',
    'MojoShellApplication',
    'chromium',
]

MAPPING_PREFIX = '--map-origin='


def _ExitIfNeeded(process):
  '''Exits |process| if it is still alive.'''
  if process.poll() is None:
    process.kill()


class AndroidShell(object):
  '''
  Used to set up and run a given mojo shell binary on an Android device.
  |config| is the mopy.config.Config for the build.
  '''
  def __init__(self, config, chrome_root):
    self.adb_path = constants.GetAdbPath()
    self.config = config
    self.paths = Paths(config, chrome_root)
    self.device = None
    self.shell_args = []
    self.target_package = apk_helper.GetPackageName(self.paths.apk_path)
    self.temp_gdb_dir = None
    # This is used by decive_utils.Install to check if the apk needs updating.
    constants.SetOutputDirectory(self.paths.build_dir)

  # TODO(msw): Use pylib's adb_wrapper and device_utils instead.
  def _CreateADBCommand(self, args):
    adb_command = [self.adb_path, '-s', self.device.adb.GetDeviceSerial()]
    adb_command.extend(args)
    logging.getLogger().debug('Command: %s', ' '.join(adb_command))
    return adb_command

  def _ReadFifo(self, path, pipe, on_fifo_closed, max_attempts=5):
    '''
    Reads the fifo at |path| on the device and write the contents to |pipe|.
    Calls |on_fifo_closed| when the fifo is closed. This method will try to find
    the path up to |max_attempts|, waiting 1 second between each attempt. If it
    cannot find |path|, a exception will be raised.
    '''
    def Run():
      def _WaitForFifo():
        for _ in xrange(max_attempts):
          if self.device.FileExists(path):
            return
          time.sleep(1)
        on_fifo_closed()
        raise Exception('Unable to find fifo: %s' % path)
      _WaitForFifo()
      stdout_cat = subprocess.Popen(self._CreateADBCommand([
                                      'shell',
                                      'cat',
                                      path]),
                                    stdout=pipe)
      atexit.register(_ExitIfNeeded, stdout_cat)
      stdout_cat.wait()
      on_fifo_closed()

    thread = threading.Thread(target=Run, name='StdoutRedirector')
    thread.start()


  def InitShell(self, device=None):
    '''
    Runs adb as root, and installs the apk as needed.  |device| is the target
    device to run on, if multiple devices are connected. Returns 0 on success or
    a non-zero exit code on a terminal failure.
    '''
    try:
      devices = device_utils.DeviceUtils.HealthyDevices()
      if device:
        self.device = next((d for d in devices if d == device), None)
        if not self.device:
          raise device_errors.DeviceUnreachableError(device)
      elif devices:
        self.device = devices[0]
      else:
        raise device_errors.NoDevicesError()

      logging.getLogger().debug('Using device: %s', self.device)
      # Clean the logs on the device to avoid displaying prior activity.
      subprocess.check_call(self._CreateADBCommand(['logcat', '-c']))
      self.device.EnableRoot()
      self.device.Install(self.paths.apk_path)
    except base_error.BaseError as e:
      # Report 'device not found' as infra failures. See http://crbug.com/493900
      print 'Exception in AndroidShell.InitShell:\n%s' % str(e)
      if e.is_infra_error or 'error: device not found' in str(e):
        return constants.INFRA_EXIT_CODE
      return constants.ERROR_EXIT_CODE

    return 0

  def _GetProcessId(self, process):
    '''Returns the process id of the process on the remote device.'''
    while True:
      line = process.stdout.readline()
      pid_command = 'launcher waiting for GDB. pid: '
      index = line.find(pid_command)
      if index != -1:
        return line[index + len(pid_command):].strip()
    return 0

  def _GetLocalGdbPath(self):
    '''Returns the path to the android gdb.'''
    if self.config.target_cpu == 'arm':
      return os.path.join(constants.ANDROID_NDK_ROOT, 'toolchains',
                          'arm-linux-androideabi-4.9', 'prebuilt',
                          'linux-x86_64', 'bin', 'arm-linux-androideabi-gdb')
    elif self.config.target_cpu == 'x86':
      return os.path.join(constants.ANDROID_NDK_ROOT, 'toolchains',
                          'x86-4.9', 'prebuilt', 'linux-x86_64', 'bin',
                          'i686-linux-android-gdb')
    elif self.config.target_cpu == 'x64':
      return os.path.join(constants.ANDROID_NDK_ROOT, 'toolchains',
                          'x86_64-4.9', 'prebuilt', 'linux-x86_64', 'bin',
                          'x86_64-linux-android-gdb')
    else:
      raise Exception('Unknown target_cpu: %s' % self.config.target_cpu)

  def _WaitForProcessIdAndStartGdb(self, process):
    '''
    Waits until we see the process id from the remote device, starts up
    gdbserver on the remote device, and gdb on the local device.
    '''
    # Wait until we see 'PID'
    pid = self._GetProcessId(process)
    assert pid != 0
    # No longer need the logcat process.
    process.kill()
    # Disable python's processing of SIGINT while running gdb. Otherwise
    # control-c doesn't work well in gdb.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    gdbserver_process = subprocess.Popen(self._CreateADBCommand(['shell',
                                                                 'gdbserver',
                                                                 '--attach',
                                                                 ':5039',
                                                                 pid]))
    atexit.register(_ExitIfNeeded, gdbserver_process)

    gdbinit_path = os.path.join(self.temp_gdb_dir, 'gdbinit')
    _CreateGdbInit(self.temp_gdb_dir, gdbinit_path, self.paths.build_dir)

    # Wait a second for gdb to start up on the device. Without this the local
    # gdb starts before the remote side has registered the port.
    # TODO(sky): maybe we should try a couple of times and then give up?
    time.sleep(1)

    local_gdb_process = subprocess.Popen([self._GetLocalGdbPath(),
                                          '-x',
                                          gdbinit_path],
                                         cwd=self.temp_gdb_dir)
    atexit.register(_ExitIfNeeded, local_gdb_process)
    local_gdb_process.wait()
    signal.signal(signal.SIGINT, signal.SIG_DFL)

  def StartActivity(self,
                    activity_name,
                    arguments,
                    stdout,
                    on_fifo_closed,
                    temp_gdb_dir=None):
    '''
    Starts the shell with the given |arguments|, directing output to |stdout|.
    |on_fifo_closed| will be run if the FIFO can't be found or when it's closed.
    |temp_gdb_dir| is set to a location with appropriate symlinks for gdb to
    find when attached to the device's remote process on startup.
    '''
    assert self.device
    arguments += self.shell_args

    cmd = self._CreateADBCommand([
           'shell',
           'am',
           'start',
           '-S',
           '-a', 'android.intent.action.VIEW',
           '-n', '%s/%s.%s' % (self.target_package,
                               self.target_package,
                               activity_name)])

    logcat_process = None
    if temp_gdb_dir:
      self.temp_gdb_dir = temp_gdb_dir
      arguments.append('--wait-for-debugger')
      # Remote debugging needs a port forwarded.
      self.device.adb.Forward('tcp:5039', 'tcp:5039')
      logcat_process = self.ShowLogs(stdout=subprocess.PIPE)

    fifo_path = '/data/data/%s/stdout.fifo' % self.target_package
    subprocess.check_call(self._CreateADBCommand(
        ['shell', 'rm', '-f', fifo_path]))
    arguments.append('--fifo-path=%s' % fifo_path)
    max_attempts = 200 if '--wait-for-debugger' in arguments else 5
    self._ReadFifo(fifo_path, stdout, on_fifo_closed, max_attempts)

    # Extract map-origin args and add the extras array with commas escaped.
    parameters = [a for a in arguments if not a.startswith(MAPPING_PREFIX)]
    parameters = [p.replace(',', r'\,') for p in parameters]
    cmd += ['--esa', '%s.extras' % self.target_package, ','.join(parameters)]

    atexit.register(self.kill)
    with open(os.devnull, 'w') as devnull:
      cmd_process = subprocess.Popen(cmd, stdout=devnull)
      if logcat_process:
        self._WaitForProcessIdAndStartGdb(logcat_process)
      cmd_process.wait()

  def kill(self):
    '''Stops the mojo shell; matches the Popen.kill method signature.'''
    self.device.ForceStop(self.target_package)

  def ShowLogs(self, stdout=sys.stdout):
    '''Displays the mojo shell logs and returns the process reading the logs.'''
    logcat = subprocess.Popen(self._CreateADBCommand([
                               'logcat',
                               '-s',
                               ' '.join(LOGCAT_TAGS)]),
                              stdout=stdout)
    atexit.register(_ExitIfNeeded, logcat)
    return logcat


def _CreateGdbInit(tmp_dir, gdb_init_path, build_dir):
  '''
  Creates the gdbinit file.

  Args:
    tmp_dir: the directory where the gdbinit and other files lives.
    gdb_init_path: path to gdbinit
    build_dir: path where build files are located.
  '''
  gdbinit = ('target remote localhost:5039\n'
             'def reload-symbols\n'
             '  set solib-search-path %s:%s\n'
             'end\n'
             'def info-symbols\n'
             '  info sharedlibrary\n'
             'end\n'
             'reload-symbols\n'
             'echo \\n\\n'
             'You are now in gdb and need to type continue (or c) to continue '
             'execution.\\n'
             'gdb is in the directory %s\\n'
             'The following functions have been defined:\\n'
             'reload-symbols: forces reloading symbols. If after a crash you\\n'
             'still do not see symbols you likely need to create a link in\\n'
             'the directory you are in.\\n'
             'info-symbols: shows status of current shared libraries.\\n'
             'NOTE: you may need to type reload-symbols again after a '
             'crash.\\n\\n' % (tmp_dir, build_dir, tmp_dir))
  with open(gdb_init_path, 'w') as f:
    f.write(gdbinit)
