#!/usr/bin/python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs the unit test suite for perf dashboard."""

import argparse
import dev_appserver
import logging
import os
import sys
import unittest

_DASHBOARD_PARENT = os.path.join(os.path.dirname(__file__))
_DASHBOARD = os.path.join(_DASHBOARD_PARENT, 'dashboard')


def _GetTests(args):
  loader = unittest.TestLoader()
  if args.tests:
    return loader.loadTestsFromNames(args.tests)
  return loader.discover(_DASHBOARD, pattern='*_test.py')


def _FixPath():
  dev_appserver.fix_sys_path()
  sys.path.insert(0, os.path.dirname(__file__))
  # Loading __init__.py when importing dashboard adds libraries to sys.path.
  import dashboard  # pylint: disable=unused-variable


def main():
  _FixPath()
  parser = argparse.ArgumentParser(description='Run the test suite.')
  parser.add_argument('tests', nargs='*', help='Fully-qualified test name.')
  parser.add_argument('-v', '--verbose', action='store_true')
  args = parser.parse_args()
  tests = _GetTests(args)
  runner_verbosity = 2
  if not args.verbose:
    runner_verbosity = 1
    logging.basicConfig(format='', level=logging.CRITICAL)
  runner = unittest.TextTestRunner(verbosity=runner_verbosity)
  result = runner.run(tests)
  return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
  sys.exit(main())
