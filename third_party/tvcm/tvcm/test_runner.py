#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import inspect
import unittest
import sys
import os
import optparse

__all__ = []

def FilterSuite(suite, predicate):
  new_suite = suite.__class__()

  for x in suite:
    if isinstance(x, unittest.TestSuite):
      subsuite = FilterSuite(x, predicate)
      if subsuite.countTestCases() == 0:
        continue

      new_suite.addTest(subsuite)
      continue

    assert isinstance(x, unittest.TestCase)
    if predicate(x):
      new_suite.addTest(x)

  return new_suite

class _TestLoader(unittest.TestLoader):
  def __init__(self, *args):
    super(_TestLoader, self).__init__(*args)
    self.discover_calls = []

  def loadTestsFromModule(self, module, use_load_tests=True):
    if module.__file__ != __file__:
      return super(_TestLoader, self).loadTestsFromModule(module, use_load_tests)

    suite = unittest.TestSuite()
    for discover_args in self.discover_calls:
      subsuite = self.discover(*discover_args)
      suite.addTest(subsuite)
    return suite

class _RunnerImpl(unittest.TextTestRunner):
  def __init__(self, filters):
    super(_RunnerImpl, self).__init__(verbosity=2)
    self.filters = filters

  def ShouldTestRun(self, test):
    if len(self.filters) == 0:
      return True
    found = False
    for name in self.filters:
      if name in test.id():
        found = True
    return found

  def run(self, suite):
    filtered_test = FilterSuite(suite, self.ShouldTestRun)
    return super(_RunnerImpl, self).run(filtered_test)

PY_ONLY_TESTS=False
BROWSER_TYPE_TO_USE='any'


class TestRunner(object):
  def __init__(self):
    self._loader = _TestLoader()

  def AddModule(self, module, pattern="*unittest.py"):
    assert inspect.ismodule(module)
    module_file_basename = os.path.splitext(os.path.basename(module.__file__))[0]
    if module_file_basename != '__init__':
      raise NotImplementedError('Modules that are one file are not supported, only directories.')

    file_basename = os.path.basename(os.path.dirname(module.__file__))
    module_first_dir = module.__name__.split('.')[0]
    assert file_basename == module_first_dir, 'Module must be toplevel'

    start_dir = os.path.dirname(module.__file__)
    top_dir = os.path.normpath(os.path.join(os.path.dirname(module.__file__), '..'))
    self._loader.discover_calls.append((start_dir, pattern, top_dir))

  def Main(self, argv=None):
    if argv == None:
      argv = sys.argv

    parser = optparse.OptionParser()
    parser.add_option('--py-only', action='store_true',
                      help='Runs only python based tests')
    parser.add_option('--browser',
                      default='any',
                      dest='browser_type',
                      help='Which browser to use for tests. Use --browser=list for options.')
    options, args = parser.parse_args(argv[1:])
    if options.browser_type == 'list':
      import browser_controller
      parser.error('Supported browsers: %s\n' %
                   browser_controller.GetAvailableBrowserTypes())

    global BROWSER_TYPE_TO_USE
    BROWSER_TYPE_TO_USE = options.browser_type

    global PY_ONLY_TESTS
    PY_ONLY_TESTS = options.py_only

    runner = _RunnerImpl(filters=args)
    return unittest.main(module=__name__, argv=[sys.argv[0]],
                         testLoader=self._loader,
                         testRunner=runner)
