# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides stubs for os, sys and subprocess for testing

This test allows one to test code that itself uses os, sys, and subprocess.
"""

import os
import re
import shlex
import sys


class Override(object):
  def __init__(self, base_module, module_list):
    stubs = {'adb_commands': AdbCommandsModuleStub,
             'cloud_storage': CloudStorageModuleStub,
             'open': OpenFunctionStub,
             'os': OsModuleStub,
             'perf_control': PerfControlModuleStub,
             'raw_input': RawInputFunctionStub,
             'subprocess': SubprocessModuleStub,
             'sys': SysModuleStub,
             'thermal_throttle': ThermalThrottleModuleStub,
    }
    self.adb_commands = None
    self.os = None
    self.subprocess = None
    self.sys = None

    self._base_module = base_module
    self._overrides = {}

    for module_name in module_list:
      self._overrides[module_name] = getattr(base_module, module_name, None)
      setattr(self, module_name, stubs[module_name]())
      setattr(base_module, module_name, getattr(self, module_name))

    if self.os and self.sys:
      self.os.path.sys = self.sys

  def __del__(self):
    assert not len(self._overrides)

  def Restore(self):
    for module_name, original_module in self._overrides.iteritems():
      setattr(self._base_module, module_name, original_module)
    self._overrides = {}


class AdbCommandsModuleStub(object):
  class AdbCommandsStub(object):
    def __init__(self, module, device):
      self._module = module
      self._device = device
      self.is_root_enabled = True

    def RunShellCommand(self, args):
      if isinstance(args, basestring):
        args = shlex.split(args)
      handler = self._module.shell_command_handlers[args[0]]
      return handler(args)

    def IsRootEnabled(self):
      return self.is_root_enabled

    def RestartAdbdOnDevice(self):
      pass

    def IsUserBuild(self):
      return False

    def WaitForDevicePm(self):
      pass

  def __init__(self):
    self.attached_devices = []
    self.shell_command_handlers = {}

    def AdbCommandsStubConstructor(device=None):
      return AdbCommandsModuleStub.AdbCommandsStub(self, device)
    self.AdbCommands = AdbCommandsStubConstructor

  @staticmethod
  def IsAndroidSupported():
    return True

  def GetAttachedDevices(self):
    return self.attached_devices

  def SetupPrebuiltTools(self, _):
    return True

  def CleanupLeftoverProcesses(self):
    pass


class CloudStorageModuleStub(object):
  INTERNAL_BUCKET = None
  PUBLIC_BUCKET = None

  class CloudStorageError(Exception):
    pass

  def __init__(self):
    self.remote_paths = []
    self.local_file_hashes = {}
    self.local_hash_files = {}

  def List(self, _):
    return self.remote_paths

  def Insert(self, bucket, remote_path, local_path):
    pass

  def CalculateHash(self, file_path):
    return self.local_file_hashes[file_path]

  def ReadHash(self, hash_path):
    return self.local_hash_files[hash_path]


class OpenFunctionStub(object):
  class FileStub(object):
    def __init__(self, data):
      self._data = data

    def __enter__(self):
      return self

    def __exit__(self, *args):
      pass

    def read(self, size=None):
      if size:
        return self._data[:size]
      else:
        return self._data

    def write(self, data):
      self._data.write(data)

    def close(self):
      pass

  def __init__(self):
    self.files = {}

  def __call__(self, name, *args, **kwargs):
    return OpenFunctionStub.FileStub(self.files[name])


class OsModuleStub(object):
  class OsEnvironModuleStub(object):
    def get(self, _):
      return None

  class OsPathModuleStub(object):
    def __init__(self, sys_module):
      self.sys = sys_module
      self.files = []

    def exists(self, path):
      return path in self.files

    def isfile(self, path):
      return path in self.files

    def join(self, *paths):
      def IsAbsolutePath(path):
        if self.sys.platform.startswith('win'):
          return re.match('[a-zA-Z]:\\\\', path)
        else:
          return path.startswith('/')

      # Per Python specification, if any component is an absolute path,
      # discard previous components.
      for index, path in reversed(list(enumerate(paths))):
        if IsAbsolutePath(path):
          paths = paths[index:]
          break

      if self.sys.platform.startswith('win'):
        tmp = os.path.join(*paths)
        return tmp.replace('/', '\\')
      else:
        tmp = os.path.join(*paths)
        return tmp.replace('\\', '/')

    @staticmethod
    def expanduser(path):
      return os.path.expanduser(path)

    @staticmethod
    def dirname(path):
      return os.path.dirname(path)

    @staticmethod
    def splitext(path):
      return os.path.splitext(path)

  X_OK = os.X_OK

  pathsep = os.pathsep

  def __init__(self, sys_module=sys):
    self.path = OsModuleStub.OsPathModuleStub(sys_module)
    self.environ = OsModuleStub.OsEnvironModuleStub()
    self.display = ':0'
    self.local_app_data = None
    self.sys_path = None
    self.program_files = None
    self.program_files_x86 = None
    self.devnull = os.devnull

  def access(self, path, _):
    return path in self.path.files

  def getenv(self, name, value=None):
    if name == 'DISPLAY':
      env = self.display
    elif name == 'LOCALAPPDATA':
      env = self.local_app_data
    elif name == 'PATH':
      env = self.sys_path
    elif name == 'PROGRAMFILES':
      env = self.program_files
    elif name == 'PROGRAMFILES(X86)':
      env = self.program_files_x86
    else:
      raise NotImplementedError('Unsupported getenv')
    return env if env else value


class PerfControlModuleStub(object):
  class PerfControlStub(object):
    def __init__(self, adb):
      pass

  def __init__(self):
    self.PerfControl = PerfControlModuleStub.PerfControlStub


class RawInputFunctionStub(object):
  def __init__(self):
    self.input = ''

  def __call__(self, name, *args, **kwargs):
    return self.input


class SubprocessModuleStub(object):
  class PopenStub(object):
    def __init__(self):
      self.communicate_result = ('', '')

    def __call__(self, args, **kwargs):
      return self

    def communicate(self):
      return self.communicate_result

  def __init__(self):
    self.Popen = SubprocessModuleStub.PopenStub()
    self.PIPE = None

  def call(self, *args, **kwargs):
    pass


class SysModuleStub(object):
  def __init__(self):
    self.platform = ''


class ThermalThrottleModuleStub(object):
  class ThermalThrottleStub(object):
    def __init__(self, adb):
      pass

  def __init__(self):
    self.ThermalThrottle = ThermalThrottleModuleStub.ThermalThrottleStub
