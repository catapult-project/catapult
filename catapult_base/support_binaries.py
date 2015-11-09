# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import stat

from catapult_base import cloud_storage
from telemetry.internal.util import path


def _GetBinPath(binary_name, arch_name, platform_name):
  return os.path.join(
      path.GetTelemetryDir(), 'bin', platform_name, arch_name, binary_name)


def _IsInCloudStorage(binary_name, arch_name, platform_name):
  return os.path.exists(
      _GetBinPath(binary_name, arch_name, platform_name) + '.sha1')


def FindLocallyBuiltPath(binary_name):
  """Finds the most recently built |binary_name|."""
  command = None
  command_mtime = 0
  chrome_root = path.GetChromiumSrcDir()
  required_mode = os.X_OK
  if binary_name.endswith('.apk'):
    required_mode = os.R_OK
  for build_dir, build_type in path.GetBuildDirectories():
    candidate = os.path.join(chrome_root, build_dir, build_type, binary_name)
    if os.path.isfile(candidate) and os.access(candidate, required_mode):
      candidate_mtime = os.stat(candidate).st_mtime
      if candidate_mtime > command_mtime:
        command = candidate
        command_mtime = candidate_mtime
  return command


def FindPath(binary_name, arch_name, platform_name):
  """Returns the path to the given binary name, pulling from the cloud if
  necessary."""
  if platform_name == 'win':
    binary_name += '.exe'
  command = FindLocallyBuiltPath(binary_name)
  if not command and _IsInCloudStorage(binary_name, arch_name, platform_name):
    logging.info('checking cloud_storage')
    command = _GetBinPath(binary_name, arch_name, platform_name)
    cloud_storage.GetIfChanged(
        command, cloud_storage.PUBLIC_BUCKET)

    # Ensure the downloaded file is actually executable.
    if command and os.path.exists(command):
      os.chmod(command,
               stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP)
  if not command and platform_name == 'win' and arch_name != 'AMD64':
    # This is an awful, awful hack to temporarily fix cloud_storage downloads
    # on XP until the binary_manager is finished and migrated to.
    # Please don't try this at home.
    return FindPath(binary_name, 'AMD64', platform_name)

  # Return an absolute path consistently.
  if command:
    command = os.path.abspath(command)
  logging.info('SupportBinaries found path: %s for binary: %s on arch: %s and '
               'platform :%s' % (command, binary_name, arch_name,
                                 platform_name))
  return command
