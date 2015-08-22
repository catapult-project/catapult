# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import platform
import sys
import unittest

from telemetry.internal.util import find_dependencies
from telemetry.internal.util import path


_TELEMETRY_DEPS_PATH = os.path.join(
    path.GetTelemetryDir(), 'telemetry', 'TELEMETRY_DEPS')


def _GetCurrentTelemetryDependencies():
  parser = find_dependencies.FindDependenciesCommand.CreateParser()
  find_dependencies.FindDependenciesCommand.AddCommandLineArgs(parser, None)
  options, args = parser.parse_args([''])
  options.positional_args = args
  return find_dependencies.FindDependencies([], options=options)


def _GetRestrictedTelemetryDeps():
  with open(_TELEMETRY_DEPS_PATH, 'r') as f:
    telemetry_deps = json.load(f)

  # Normalize paths in telemetry_deps since TELEMETRY_DEPS file only contain
  # the relative path in chromium/src/.
  def NormalizePath(p):
    p = p.replace('/', os.path.sep)
    return os.path.realpath(os.path.join(path.GetChromiumSrcDir(), p))

  telemetry_deps['file_deps'] = [
      NormalizePath(p) for p in telemetry_deps['file_deps']]
  telemetry_deps['directory_deps'] = [
      NormalizePath(p) for p in telemetry_deps['directory_deps']]
  return telemetry_deps


class TelemetryDependenciesTest(unittest.TestCase):

  def testNoNewTelemetryDependencies(self):
    telemetry_deps = _GetRestrictedTelemetryDeps()
    current_dependencies = _GetCurrentTelemetryDependencies()
    extra_dep_paths = []
    for dep_path in current_dependencies:
      if not (dep_path in telemetry_deps['file_deps'] or
              any(path.IsSubpath(dep_path, d)
                  for d in telemetry_deps['directory_deps'])):
        extra_dep_paths.append(dep_path)
    # Temporarily ignore failure on Mac because test is failing on Mac 10.8 bot.
    # crbug.com/522335
    if extra_dep_paths:
      if platform.system() != 'Darwin':
        self.fail(
            'Your patch adds new dependencies to telemetry. Please contact '
            'aiolos@,dtu@, or nednguyen@ on how to proceed with this change. '
            'Extra dependencies:\n%s' % '\n'.join(extra_dep_paths))
      else:
        print ('Dependencies check failed on mac platform. Extra deps: %s\n'
               ' sys.path: %s' % (extra_dep_paths, sys.path))
