# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(yzshen): Once the dep manager is ready, remove this file and use the one
# from src/mojo/tools directly.


import ast
import os.path
import platform
import re
import sys


class Config(object):
  '''A Config contains a dictionary that species a build configuration.'''

  # Valid values for target_os:
  OS_ANDROID = 'android'
  OS_CHROMEOS = 'chromeos'
  OS_LINUX = 'linux'
  OS_MAC = 'mac'
  OS_WINDOWS = 'windows'

  # Valid values for target_cpu:
  ARCH_X86 = 'x86'
  ARCH_X64 = 'x64'
  ARCH_ARM = 'arm'

  def __init__(self, build_dir=None, target_os=None, target_cpu=None,
               is_debug=None, is_verbose=None, apk_name='MojoRunner.apk'):
    '''Function arguments take precedence over GN args and default values.'''
    assert target_os in (None, Config.OS_ANDROID, Config.OS_CHROMEOS,
                         Config.OS_LINUX, Config.OS_MAC, Config.OS_WINDOWS)
    assert target_cpu in (None, Config.ARCH_X86, Config.ARCH_X64,
                          Config.ARCH_ARM)
    assert is_debug in (None, True, False)
    assert is_verbose in (None, True, False)

    self.values = {
      'build_dir': build_dir,
      'target_os': self.GetHostOS(),
      'target_cpu': self.GetHostCPU(),
      'is_debug': True,
      'is_verbose': True,
      'dcheck_always_on': False,
      'is_asan': False,
      'apk_name': apk_name,
    }

    self._ParseGNArgs()
    if target_os is not None:
      self.values['target_os'] = target_os
    if target_cpu is not None:
      self.values['target_cpu'] = target_cpu
    if is_debug is not None:
      self.values['is_debug'] = is_debug
    if is_verbose is not None:
      self.values['is_verbose'] = is_verbose

  @staticmethod
  def GetHostOS():
    if sys.platform == 'linux2':
      return Config.OS_LINUX
    if sys.platform == 'darwin':
      return Config.OS_MAC
    if sys.platform == 'win32':
      return Config.OS_WINDOWS
    raise NotImplementedError('Unsupported host OS')

  @staticmethod
  def GetHostCPU():
    # Derived from //native_client/pynacl/platform.py
    machine = platform.machine()
    if machine in ('x86', 'x86-32', 'x86_32', 'x8632', 'i386', 'i686', 'ia32',
                   '32'):
      return Config.ARCH_X86
    if machine in ('x86-64', 'amd64', 'AMD64', 'x86_64', 'x8664', '64'):
      return Config.ARCH_X64
    if machine.startswith('arm'):
      return Config.ARCH_ARM
    raise Exception('Cannot identify CPU arch: %s' % machine)

  def _ParseGNArgs(self):
    '''Parse the gn config file from the build directory, if it exists.'''
    TRANSLATIONS = {'true': 'True', 'false': 'False',}
    if self.values['build_dir'] is None:
      return
    gn_file = os.path.join(self.values['build_dir'], 'args.gn')
    if not os.path.isfile(gn_file):
      return

    with open(gn_file, 'r') as f:
      for line in f:
        line = re.sub(r'\s*#.*', '', line)
        result = re.match(r'^\s*(\w+)\s*=\s*(.*)\s*$', line)
        if result:
          key = result.group(1)
          value = result.group(2)
          self.values[key] = ast.literal_eval(TRANSLATIONS.get(value, value))

  # Getters for standard fields ------------------------------------------------

  @property
  def build_dir(self):
    '''Build directory path.'''
    return self.values['build_dir']

  @property
  def target_os(self):
    '''OS of the build/test target.'''
    return self.values['target_os']

  @property
  def target_cpu(self):
    '''CPU arch of the build/test target.'''
    return self.values['target_cpu']

  @property
  def is_debug(self):
    '''Is Debug build?'''
    return self.values['is_debug']

  @property
  def is_verbose(self):
    '''Should print additional logging information?'''
    return self.values['is_verbose']

  @property
  def dcheck_always_on(self):
    '''DCHECK and MOJO_DCHECK are fatal even in release builds'''
    return self.values['dcheck_always_on']

  @property
  def is_asan(self):
    '''Is ASAN build?'''
    return self.values['is_asan']

  @property
  def apk_name(self):
    '''Name of the APK file to run'''
    return self.values['apk_name']
