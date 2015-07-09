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
  sys.path.append(os.path.dirname(__file__))
  # The __init__.py in the dashboard package should add third party
  # libraries to the path.
  import dashboard  # pylint: disable=unused-variable


def main():
  _FixPath()
  parser = argparse.ArgumentParser(description='Run the test suite.')
  parser.add_argument(
      'tests', nargs='*', help='Fully-qualified names of tests to run.')
  args = parser.parse_args()
  runner = unittest.TextTestRunner(verbosity=1)
  logging.basicConfig(level=logging.CRITICAL)
  result = runner.run(_GetTests(args))
  if result.wasSuccessful():
    sys.exit(0)
  else:
    sys.exit(1)


if __name__ == '__main__':
  main()
