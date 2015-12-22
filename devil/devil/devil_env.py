# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json
import logging
import os
import platform
import sys
import tempfile
import threading

# TODO(jbudorick): Update this once dependency_manager moves to catapult.
CATAPULT_BASE_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir,
    'tools', 'telemetry'))

@contextlib.contextmanager
def SysPath(path):
  sys.path.append(path)
  yield
  if sys.path[-1] != path:
    logging.debug('Expected %s at the end of sys.path. Full sys.path: %s',
                  path, str(sys.path))
    sys.path.remove(path)
  else:
    sys.path.pop()

with SysPath(CATAPULT_BASE_PATH):
  from catapult_base import dependency_manager # pylint: disable=import-error

_ANDROID_BUILD_TOOLS = {'aapt', 'dexdump', 'split-select'}

_DEVIL_DEFAULT_CONFIG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'devil_dependencies.json'))

_LEGACY_ENVIRONMENT_VARIABLES = {
  'ADB_PATH': {
    'dependency_name': 'adb',
    'platform': 'linux_x86_64',
  },
  'ANDROID_SDK_ROOT': {
    'dependency_name': 'android_sdk',
    'platform': 'linux_x86_64',
  },
}


def _GetEnvironmentVariableConfig():
  path_config = (
      (os.environ.get(k), v)
      for k, v in _LEGACY_ENVIRONMENT_VARIABLES.iteritems())
  return {
    'config_type': 'BaseConfig',
    'dependencies': {
      c['dependency_name']: {
        'file_info': {
          c['platform']: {
            'local_paths': [p],
          },
        },
      } for p, c in path_config if p
    },
  }


class _Environment(object):

  def __init__(self):
    self._dm_init_lock = threading.Lock()
    self._dm = None

  def Initialize(self, configs=None, config_files=None):
    """Initialize devil's environment from configuration files.

    This uses all configurations provided via |configs| and |config_files|
    to determine the locations of devil's dependencies. Configurations should
    all take the form described by catapult_base.dependency_manager.BaseConfig.
    If no configurations are provided, a default one will be used if available.

    Args:
      configs: An optional list of dict configurations.
      config_files: An optional list of files to load
    """

    # Make sure we only initialize self._dm once.
    with self._dm_init_lock:
      if self._dm is None:
        if configs is None:
          configs = []

        env_config = _GetEnvironmentVariableConfig()
        if env_config:
          configs.insert(0, env_config)
        self._InitializeRecursive(
            configs=configs,
            config_files=config_files)
        assert self._dm is not None, 'Failed to create dependency manager.'

  def _InitializeRecursive(self, configs=None, config_files=None):
    # This recurses through configs to create temporary files for each and
    # take advantage of context managers to appropriately close those files.
    # TODO(jbudorick): Remove this recursion if/when dependency_manager
    # supports loading configurations directly from a dict.
    if configs:
      with tempfile.NamedTemporaryFile(delete=False) as next_config_file:
        try:
          next_config_file.write(json.dumps(configs[0]))
          next_config_file.close()
          self._InitializeRecursive(
              configs=configs[1:],
              config_files=[next_config_file.name] + (config_files or []))
        finally:
          if os.path.exists(next_config_file.name):
            os.remove(next_config_file.name)
    else:
      config_files = config_files or []
      if 'DEVIL_ENV_CONFIG' in os.environ:
        config_files.append(os.environ.get('DEVIL_ENV_CONFIG'))
      config_files.append(_DEVIL_DEFAULT_CONFIG)

      self._dm = dependency_manager.DependencyManager(
          [dependency_manager.BaseConfig(c) for c in config_files])

  def FetchPath(self, dependency, arch=None, device=None):
    if self._dm is None:
      self.Initialize()
    if dependency in _ANDROID_BUILD_TOOLS:
      self.FetchPath('android_build_tools_libc++', arch=arch, device=device)
    return self._dm.FetchPath(dependency, GetPlatform(arch, device))

  def LocalPath(self, dependency, arch=None, device=None):
    if self._dm is None:
      self.Initialize()
    return self._dm.LocalPath(dependency, GetPlatform(arch, device))


def GetPlatform(arch=None, device=None):
  if device:
    return 'android_%s' % (arch or device.product_cpu_abi)
  return 'linux_%s' % platform.machine()


config = _Environment()

