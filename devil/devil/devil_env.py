# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys
import tempfile
import threading

# TODO(jbudorick): Update this once dependency_manager moves to catapult.
_TELEMETRY_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir,
    'tools', 'telemetry'))
sys.path.append(_TELEMETRY_PATH)
from catapult_base import dependency_manager # pylint: disable=import-error

_ANDROID_BUILD_TOOLS = {'aapt', 'dexdump', 'split-select'}

_DEVIL_DEFAULT_CONFIG = os.path.abspath(os.path.join(
    os.path.dirname(__file__), 'devil_dependencies.json'))


class _Environment(object):

  def __init__(self):
    self._config = None
    self._config_init_lock = threading.Lock()
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

    # Make sure we only initialize self._config once.
    with self._config_init_lock:
      if self._config is not None:
        return
      self._config = {}

    self._InitializeRecursive(
        configs=configs, config_files=config_files)

  def _InitializeRecursive(self, configs=None, config_files=None):
    # This recurses through configs to create temporary files for each and
    # take advantage of context managers to appropriately close those files.
    # TODO(jbudorick): Remove this recursion if/when dependency_manager
    # supports loading configurations directly from a dict.
    if configs:
      with tempfile.NamedTemporaryFile() as next_config_file:
        next_config_file.write(json.dumps(configs[0]))
        next_config_file.flush()
        self._InitializeRecursive(
            configs=configs[1:],
            config_files=[next_config_file.name] + (config_files or []))
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
    return self._dm.FetchPath(dependency, _GetPlatform(arch, device))

  def LocalPath(self, dependency, arch=None, device=None):
    if self._dm is None:
      self.Initialize()
    return self._dm.LocalPath(dependency, _GetPlatform(arch, device))


def _GetPlatform(arch, device):
  if not arch:
    arch = device.product_cpu_abi if device else 'host'
  return 'android_%s' % arch


config = _Environment()

