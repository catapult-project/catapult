#!/usr/bin/python

"""Runs the unit test suite for perf dashboard."""

import argparse
import dev_appserver
import os
import sys
import unittest

_DASHBOARD = os.path.join(os.path.dirname(__file__), 'dashboard')


def _GetTests(args):
  loader = unittest.TestLoader()
  if args.tests:
    return loader.loadTestsFromNames(args.tests)
  return loader.discover(_DASHBOARD, pattern='*_test.py')


def main():
  dev_appserver.fix_sys_path()
  parser = argparse.ArgumentParser(description='Run the test suite.')
  parser.add_argument(
      'tests', nargs='*', help='Fully-qualified names of tests to run.')
  args = parser.parse_args()
  runner = unittest.TextTestRunner(verbosity=1)
  runner.run(_GetTests(args))


if __name__ == '__main__':
  main()
