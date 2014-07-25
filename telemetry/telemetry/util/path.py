# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util


# TODO(dtu): Move these functions from core.util to here.
GetBaseDir = util.GetBaseDir
GetTelemetryDir = util.GetTelemetryDir
GetUnittestDataDir = util.GetUnittestDataDir
GetChromiumSrcDir = util.GetChromiumSrcDir
AddDirToPythonPath = util.AddDirToPythonPath
GetBuildDirectories = util.GetBuildDirectories


def IsExecutable(path):
  return os.path.isfile(path) and os.access(path, os.X_OK)


def FindInstalledWindowsApplication(application_path):
  """Search common Windows installation directories for an application.

  Args:
    application_path: Path to application relative from installation location.
  Returns:
    A string representing the full path, or None if not found.
  """
  search_paths = [os.getenv('PROGRAMFILES(X86)'),
                  os.getenv('PROGRAMFILES'),
                  os.getenv('LOCALAPPDATA')]
  search_paths += os.getenv('PATH', '').split(os.pathsep)

  for search_path in search_paths:
    if not search_path:
      continue
    path = os.path.join(search_path, application_path)
    if IsExecutable(path):
      return path

  return None
