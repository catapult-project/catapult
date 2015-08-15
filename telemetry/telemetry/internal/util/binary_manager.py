# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#TODO(aiolos): Remove the debug logging once the entire Dependency Manager
#system has landed.
import logging
import os

from catapult_base import support_binaries
from catapult_base import dependency_manager
from telemetry.core import exceptions
from telemetry.core import util


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
  config_files = [TELEMETRY_PROJECT_CONFIG]
  if environment_config:
    config_files.append(environment_config)
  logging.debug('Initializing the dependency manager with config files: %s.'
                % config_files)
  _dependency_manager = dependency_manager.DependencyManager(config_files)
  logging.debug('Successfully initialized the dependency manager.')


def FetchPath(binary_name, platform, arch):
  """ Return a path to the appropriate executable for <binary_name>, downloading
      from cloud storage if needed, or None if it cannot be found.
  """
  logging.debug('Called FetchPath for binary: %s on platform: %s and arch: %s'
                % (binary_name, platform, arch))
  if _dependency_manager is None:
    raise exceptions.InitializationError(
        'Called FetchPath with uninitialized binary manager.')
  return support_binaries.FindPath(binary_name, platform, arch)


def LocalPath(binary_name, platform, arch):
  """ Return a local path to the given binary name, or None if an executable
      cannot be found. Will not download the executable.
      """
  logging.debug('Called LocalPath for binary: %s on platform: %s and arch: '
                '%s' % (binary_name, platform, arch))
  if _dependency_manager is None:
    raise exceptions.InitializationError(
        'Called LocalPath with uninitialized binary manager.')
  del platform, arch
  return support_binaries.FindLocallyBuiltPath(binary_name)
