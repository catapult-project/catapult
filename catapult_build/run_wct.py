# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess
import sys

def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)

_CATAPULT_PATH = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_AddToPathIfNeeded(os.path.join(_CATAPULT_PATH, 'common', 'node_runner'))
from node_runner import node_util  # pylint: disable=wrong-import-position,import-error

NODE_MODULES = node_util.GetNodeModulesPath()
RUN_WCT = os.path.join(NODE_MODULES, 'chops-wct-runner', 'src', 'run-wct.js')


def RunWct(base_dir, dep_dirs, debug=False, prefix=''):
  command = [node_util.GetNodePath(), RUN_WCT]
  command += ['--base', base_dir]
  command += ['--prefix', prefix]
  if debug:
    command += ['--debug']
  for dep in dep_dirs:
    command += ['--dep', dep]
  logging.info('Starting WCT: %r', command)
  return subprocess.call(command)
