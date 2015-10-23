# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#TODO(aiolos): Remove the debug logging once the entire Dependency Manager
#system has landed.
import logging
import os

from catapult_base import dependency_manager
from telemetry.core import exceptions
from telemetry.core import util
from devil import devil_env


TELEMETRY_PROJECT_CONFIG = os.path.join(
    util.GetTelemetryDir(), 'telemetry', 'internal', 'binary_dependencies.json')


_dependency_manager = None


def NeedsInit():
  return not _dependency_manager


def InitDependencyManager(environment_config):
  global _dependency_manager
  if _dependency_manager:
    raise exceptions.InitializationError(
        'Trying to re-initialize the binary manager with config %s'
        % environment_config)
  configs = [dependency_manager.BaseConfig(TELEMETRY_PROJECT_CONFIG)]
  if environment_config:
    configs.insert(0, dependency_manager.BaseConfig(environment_config))
  _dependency_manager = dependency_manager.DependencyManager(configs)

  devil_env.config.Initialize()


def FetchPath(binary_name, arch, platform):
  """ Return a path to the appropriate executable for <binary_name>, downloading
      from cloud storage if needed, or None if it cannot be found.
  """
  logging.info('Called FetchPath for binary: %s on platform: %s and arch: %s'
                % (binary_name, platform, arch))
  if _dependency_manager is None:
    raise exceptions.InitializationError(
        'Called FetchPath with uninitialized binary manager.')
  return _dependency_manager.FetchPath(
      binary_name, '%s_%s' % (platform, arch), try_support_binaries=True)


def LocalPath(binary_name, arch, platform):
  """ Return a local path to the given binary name, or None if an executable
      cannot be found. Will not download the executable.
      """
  logging.debug('Called LocalPath for binary: %s on platform: %s and arch: '
                '%s' % (binary_name, platform, arch))
  if _dependency_manager is None:
    raise exceptions.InitializationError(
        'Called LocalPath with uninitialized binary manager.')
  return _dependency_manager.LocalPath(
      binary_name, '%s_%s' % (platform, arch), try_support_binaries=True)
