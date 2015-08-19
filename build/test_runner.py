#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import subprocess
import sys


class bcolors(object):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def _RunTest(test, chrome_command):
  if sys.platform in test.get('disabled_platforms', {}):
    return 0
  command = [test['path']]
  if sys.platform == 'win32':
    command = ['python'] + command
  if test.get('chrome_path_arg') and chrome_command:
    command += ['--chrome_path', chrome_command]
  return subprocess.call(command)


def Main(name, tests, argv):
  parser = argparse.ArgumentParser(
      description='Run all tests of %s project.' % name)
  parser.add_argument('--chrome_path', type=str,
      help='Path to Chrome browser binary for dev_server tests.')
  args = parser.parse_args(argv[1:])

  exit_code = 0
  errors = []
  for test in tests:
    new_exit_code = _RunTest(test, args.chrome_path)
    if new_exit_code != 0:
      exit_code |= new_exit_code
      errors += '%s failed some tests. Re-run %s script to see those.\n' % (
          os.path.basename(test['path']), test['path'])

  if exit_code:
    print (bcolors.FAIL +
           'Oooops! Looks like some of your tests have failed.' +
           bcolors.ENDC), u'\U0001F631'.encode('utf-8')
    sys.stderr.writelines(errors)
  else:
    print (bcolors.OKGREEN +
           'Woho! All the tests have passed. You are awesome!' +
           bcolors.ENDC), u'\U0001F601'.encode('utf-8')

  sys.exit(exit_code)
