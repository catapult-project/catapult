# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry import decorators
from telemetry.core import util
from telemetry.util import cloud_storage


def _GetBinPath(binary_name, platform_name):
  # TODO(tonyg): Add another nesting level for architecture_name.
  return os.path.join(util.GetTelemetryDir(), 'bin', platform_name, binary_name)


def _IsInCloudStorage(binary_name, platform_name):
  return os.path.exists(_GetBinPath(binary_name, platform_name) + '.sha1')


@decorators.Cache
def FindLocallyBuiltPath(binary_name):
  """Finds the most recently built |binary_name|."""
  command = None
  command_mtime = 0
  chrome_root = util.GetChromiumSrcDir()
  required_mode = os.X_OK
  if binary_name.endswith('.apk'):
    required_mode = os.R_OK
  for build_dir, build_type in util.GetBuildDirectories():
    candidate = os.path.join(chrome_root, build_dir, build_type, binary_name)
    if os.path.isfile(candidate) and os.access(candidate, required_mode):
      candidate_mtime = os.stat(candidate).st_mtime
      if candidate_mtime > command_mtime:
        command = candidate
        command_mtime = candidate_mtime
  return command


@decorators.Cache
def FindPath(binary_name, platform_name):
  """Returns the path to the given binary name, pulling from the cloud if
  necessary."""
  if platform_name == 'win':
    binary_name += '.exe'
  command = FindLocallyBuiltPath(binary_name)
  if not command and _IsInCloudStorage(binary_name, platform_name):
    cloud_storage.GetIfChanged(_GetBinPath(binary_name, platform_name))
    command = _GetBinPath(binary_name, platform_name)
  return command
