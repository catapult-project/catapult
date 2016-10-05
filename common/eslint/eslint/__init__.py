# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import subprocess
import sys


_CATAPULT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.path.pardir, os.path.pardir, os.path.pardir)


def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)


def _UpdateSysPathIfNeeded():
  _AddToPathIfNeeded(os.path.join(_CATAPULT_PATH, 'common', 'node_runner'))
  _AddToPathIfNeeded(os.path.join(_CATAPULT_PATH, 'common', 'py_utils'))


_UpdateSysPathIfNeeded()


import py_utils
from node_runner import node_util


BASE_ESLINT_CMD = [
  node_util.GetNodePath(),
  os.path.join(node_util.GetNodeModulesPath(), 'eslint', 'bin', 'eslint.js'),
  '--color'
]


DEFAULT_ESLINT_CONFIG = os.path.join(
    py_utils.GetCatapultDir(), 'common', 'eslint', '.eslintrc')


DEFAULT_ESLINT_RULES_DIR = os.path.join(
    py_utils.GetCatapultDir(), 'common', 'eslint', 'rules')


def _CreateEslintCommand(config, rulesdir):
  return BASE_ESLINT_CMD + [
      '--config', config,
      '--rulesdir', rulesdir
  ]


def RunEslintOnDirs(dirs,
                    config=DEFAULT_ESLINT_CONFIG,
                    rules_dir=DEFAULT_ESLINT_RULES_DIR):
  if type(dirs) is not list or len(dirs) == 0:
    raise ValueError('Must specify a non-empty list of directories to lint.')

  try:
    find_cmd = ['find'] + dirs + ['-name', '*.html']
    eslint_cmd = _CreateEslintCommand(config, rules_dir)
    p1 = subprocess.Popen(find_cmd, stdout=subprocess.PIPE)
    output = subprocess.check_output(['xargs'] + eslint_cmd, stdin=p1.stdout)
    p1.wait()
    return output
  except subprocess.CalledProcessError as e:
    return e.output


def RunEslintOnFiles(filenames,
                     config=DEFAULT_ESLINT_CONFIG,
                     rules_dir=DEFAULT_ESLINT_RULES_DIR):
  if type(filenames) is not list or len(filenames) == 0:
    raise ValueError('Must specify a non-empty list of files to lint.')

  try:
    eslint_cmd = _CreateEslintCommand(config, rules_dir)
    return subprocess.check_output(eslint_cmd + filenames,
                                   stderr=subprocess.STDOUT)
  except subprocess.CalledProcessError as e:
    return e.output
