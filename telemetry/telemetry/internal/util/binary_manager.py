# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from catapult_base import binary_manager
from dependency_manager import base_config
from dependency_manager import exceptions as dependency_manager_exceptions
from devil import devil_env

from telemetry.core import exceptions
from telemetry.core import util


TELEMETRY_PROJECT_CONFIG = os.path.join(
    util.GetTelemetryDir(), 'telemetry', 'internal', 'binary_dependencies.json')


CHROME_BINARY_CONFIG = os.path.join(util.GetCatapultDir(), 'catapult_base',
                                    'catapult_base', 'chrome_binaries.json')


NoPathFoundError = dependency_manager_exceptions.NoPathFoundError
CloudStorageError = dependency_manager_exceptions.CloudStorageError


_binary_manager = None


def NeedsInit():
  return not _binary_manager


def InitDependencyManager(environment_config):
  global _binary_manager
  if _binary_manager:
    raise exceptions.InitializationError(
        'Trying to re-initialize the binary manager with config %s'
        % environment_config)
  configs = [base_config.BaseConfig(TELEMETRY_PROJECT_CONFIG),
             base_config.BaseConfig(CHROME_BINARY_CONFIG)]
  if environment_config:
    configs.insert(0, base_config.BaseConfig(environment_config))
  _binary_manager = binary_manager.BinaryManager(configs)

  devil_env.config.Initialize()


def FetchPath(binary_name, arch, os_name, os_version=None):
  """ Return a path to the appropriate executable for <binary_name>, downloading
      from cloud storage if needed, or None if it cannot be found.
  """
  if _binary_manager is None:
    raise exceptions.InitializationError(
        'Called FetchPath with uninitialized binary manager.')
  return _binary_manager.FetchPath(binary_name, arch, os_name, os_version)


def LocalPath(binary_name, arch, os_name, os_version=None):
  """ Return a local path to the given binary name, or None if an executable
      cannot be found. Will not download the executable.
      """
  if _binary_manager is None:
    raise exceptions.InitializationError(
        'Called LocalPath with uninitialized binary manager.')
  return _binary_manager.LocalPath(binary_name, arch, os_name, os_version)
