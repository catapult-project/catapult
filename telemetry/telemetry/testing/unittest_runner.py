# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys

from telemetry.core import util


def Run(project_config, no_browser=False, stream=None):
  args = sys.argv[1:]
  assert '--top-level-dir' not in args, (
      'Top level directory for running tests should be specified through '
      'the instance of telemetry.project_config.ProjectConfig.')
  assert '--client-config' not in args, (
      'Client config file to be used for telemetry should be specified through '
      'the instance of telemetry.project_config.ProjectConfig.')
  assert project_config.top_level_dir, 'Must specify top level dir for project'
  args.extend(['--top-level-dir', project_config.top_level_dir])
  if project_config.client_config:
    args.extend(['--client-config', project_config.client_config])
  if no_browser and not '--no-browser' in args:
    args.extend(['--no-browser'])

  if project_config.default_chrome_root and not '--chrome-root' in args:
    args.extend(['--chrome-root', project_config.default_chrome_root])

  env = os.environ.copy()
  telemetry_dir = util.GetTelemetryDir()
  if 'PYTHONPATH' in env:
    env['PYTHONPATH'] = os.pathsep.join([env['PYTHONPATH'], telemetry_dir])
  else:
    env['PYTHONPATH'] = telemetry_dir

  path_to_run_tests = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                   'run_tests.py')
  return subprocess.call([sys.executable, path_to_run_tests] + args, env=env)
