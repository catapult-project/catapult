# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
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


_DEFAULT_CONFIG_FILES = [
  os.path.abspath(os.path.join(
      os.path.dirname(__file__), os.pardir, 'devil_config.json')),
]


class _Environment(object):

  def __init__(self):
    self._config = None
    self._config_init_lock = threading.Lock()

  def Initialize(self, configs=None, config_files=None):
    """Initialize devil's environment.

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

    self._InitializeRecursive(configs=configs, config_files=config_files)

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
      self._InitializeImpl(config_files)

  def _InitializeImpl(self, config_files):
    if not config_files:
      config_files = _DEFAULT_CONFIG_FILES

    dm = dependency_manager.DependencyManager(
        [dependency_manager.BaseConfig(c) for c in config_files])
    platform = 'linux_android'

    android_sdk_path = dm.FetchPath('android_sdk', platform)

    if os.path.exists(android_sdk_path):
      self._config['android_sdk_path'] = android_sdk_path

      # Chromium's hooks always download the SDK extras even if they aren't
      # downloading the SDK, so we have to check for the existence of the
      # particular components we care about.

      try:
        adb_path = dm.FetchPath('adb_path', platform)
      except dependency_manager.NoPathFoundError:
        adb_path = os.path.join(
            self.android_sdk_path, 'platform-tools', 'adb')
      if os.path.exists(adb_path):
        self._config['adb_path'] = adb_path

      build_tools_path = os.path.join(self.android_sdk_path, 'build-tools')
      if os.path.exists(build_tools_path):
        build_tools_contents = os.listdir(build_tools_path)
        if build_tools_contents:
          if len(build_tools_contents) > 1:
            build_tools_contents.sort()
            logging.warning(
                'More than one set of build-tools provided by the Android SDK:'
                ' %s', ','.join(build_tools_contents))
            logging.warning('Defaulting to %s', build_tools_contents[-1])
          self._config['android_sdk_build_tools_path'] = os.path.join(
              self.android_sdk_path, 'build-tools', build_tools_contents[-1])

    try:
      self._config['forwarder_host_path'] = dm.FetchPath(
          'forwarder_host', platform)
      self._config['forwarder_device_path'] = dm.FetchPath(
          'forwarder_device', platform)
    except dependency_manager.NoPathFoundError as e:
      logging.warning(str(e))

    try:
      self._config['md5sum_host_path'] = dm.FetchPath('md5sum_host', platform)
      self._config['md5sum_device_path'] = dm.FetchPath(
          'md5sum_device', platform)
    except dependency_manager.NoPathFoundError as e:
      logging.warning(str(e))

    try:
      self._config['pymock_path'] = dm.FetchPath('pymock', platform)
    except dependency_manager.NoPathFoundError as e:
      logging.warning(str(e))

  def __getattr__(self, name):
    if self._config is None:
      self.Initialize()

    if name not in self._config:
      raise AttributeError('devil environment has no %r attribute' % name)

    return self._config[name]


config = _Environment()


def GenerateDynamicConfig(deps):
  """Generate a configuration dict from the provided deps dict.

  Args:
    deps: A dict mapping dependency names to lists of local files.
  Returns:
    A BaseConfig-compatible dict.
  """
  return {
    'config_type': 'BaseConfig',
    'dependencies': {
      k: {
        'file_info': {
          'linux_android': {
            'local_paths': v
          }
        }
      } for k, v in deps.iteritems()
    }
  }

