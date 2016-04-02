# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import inspect
import re
import unittest

from telemetry.core import discover
from telemetry.internal.browser import browser_options
from telemetry.internal.util import binary_manager
from telemetry.testing import options_for_unittests
from telemetry.testing import serially_executed_browser_test_case


def ProcessCommandLineOptions(test_class, args):
  options = browser_options.BrowserFinderOptions()
  options.browser_type = 'any'
  parser = options.CreateParser(test_class.__doc__)
  test_class.AddCommandlineArgs(parser)
  finder_options, positional_args = parser.parse_args(args)
  finder_options.positional_args = positional_args
  options_for_unittests.Push(finder_options)
  return finder_options


def ValidateDistinctNames(browser_test_classes):
  names_to_test_classes = {}
  for cl in browser_test_classes:
    name = cl.Name()
    if name in names_to_test_classes:
      raise Exception('Test name %s is duplicated between %s and %s' % (
          name, repr(cl), repr(names_to_test_classes[name])))
    names_to_test_classes[name] = cl


def GenerateTestMethod(based_method, args):
  return lambda self: based_method(self, *args)


_INVALID_TEST_NAME_RE = re.compile(r'[^a-zA-Z0-9_]')
def ValidateTestMethodname(test_name):
  assert not bool(_INVALID_TEST_NAME_RE.search(test_name))


_TEST_GENERATOR_PREFIX = 'GenerateTestCases_'

def LoadTests(test_class, finder_options):
  test_cases = []
  for name, method in inspect.getmembers(
      test_class, predicate=inspect.ismethod):
    if name.startswith('test'):
      test_cases.append(test_class(name))
    elif name.startswith(_TEST_GENERATOR_PREFIX):
      based_method_name = name[len(_TEST_GENERATOR_PREFIX):]
      assert hasattr(test_class, based_method_name), (
          '%s is specified but %s based method %s does not exist' %
          name, based_method_name)
      based_method = getattr(test_class, based_method_name)
      for generated_test_name, args in method(finder_options):
        ValidateTestMethodname(generated_test_name)
        setattr(test_class, generated_test_name, GenerateTestMethod(
            based_method, args))
        test_cases.append(test_class(generated_test_name))
  return test_cases


def Run(project_config, args):
  binary_manager.InitDependencyManager(project_config.client_config)
  parser = argparse.ArgumentParser(description='Run a browser test suite')
  parser.add_argument('test', type=str, help='Name of the test suite to run')
  option, extra_args = parser.parse_known_args(args)

  for start_dir in project_config.start_dirs:
    modules_to_classes = discover.DiscoverClasses(
        start_dir, project_config.top_level_dir,
        base_class=serially_executed_browser_test_case.SeriallyBrowserTestCase)
    browser_test_classes = modules_to_classes.values()

  ValidateDistinctNames(browser_test_classes)

  test_class = None
  for cl in browser_test_classes:
    if cl.Name() == option.test:
      test_class = cl

  if not test_class:
    print 'Cannot find test class with name matched %s' % option.test
    print 'Available tests: %s' % '\n'.join(
        cl.Name() for cl in browser_test_classes)
    return 1

  options = ProcessCommandLineOptions(test_class, extra_args)

  suite = unittest.TestSuite()
  for test in LoadTests(test_class, options):
    suite.addTest(test)

  results = unittest.TextTestRunner(verbosity=0).run(suite)
  return len(results.failures)
