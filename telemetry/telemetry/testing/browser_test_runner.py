# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import inspect
import json
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

def LoadTests(test_class, finder_options, filter_regex_str):
  test_cases = []
  filter_regex = re.compile(filter_regex_str)
  for name, method in inspect.getmembers(
      test_class, predicate=inspect.ismethod):
    if name.startswith('test'):
      # Do not allow method names starting with "test" in these
      # subclasses, to avoid collisions with Python's unit test runner.
      raise Exception('Name collision with Python\'s unittest runner: %s' %
                      name)
    elif name.startswith('Test') and filter_regex.search(name):
      # Pass these through for the time being. We may want to rethink
      # how they are handled in the future.
      test_cases.append(test_class(name))
    elif name.startswith(_TEST_GENERATOR_PREFIX):
      based_method_name = name[len(_TEST_GENERATOR_PREFIX):]
      assert hasattr(test_class, based_method_name), (
          '%s is specified but %s based method %s does not exist' %
          name, based_method_name)
      based_method = getattr(test_class, based_method_name)
      for generated_test_name, args in method(finder_options):
        ValidateTestMethodname(generated_test_name)
        if filter_regex.search(generated_test_name):
          setattr(test_class, generated_test_name, GenerateTestMethod(
              based_method, args))
          test_cases.append(test_class(generated_test_name))
  test_cases.sort(key=lambda t: t.id())
  return test_cases


class TestRunOptions(object):
  def __init__(self):
    self.verbosity = 2


class BrowserTestResult(unittest.TextTestResult):
  def __init__(self, *args, **kwargs):
    super(BrowserTestResult, self).__init__(*args, **kwargs)
    self.successes = []

  def addSuccess(self, test):
    super(BrowserTestResult, self).addSuccess(test)
    self.successes.append(test)


def Run(project_config, test_run_options, args):
  binary_manager.InitDependencyManager(project_config.client_configs)
  parser = argparse.ArgumentParser(description='Run a browser test suite')
  parser.add_argument('test', type=str, help='Name of the test suite to run')
  parser.add_argument(
      '--write-abbreviated-json-results-to', metavar='FILENAME', action='store',
      help=('If specified, writes the full results to that path in json form.'))
  parser.add_argument('--test-filter', type=str, default='', action='store',
      help='Run only tests whose names match the given filter regexp.')
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
  for test in LoadTests(test_class, options, option.test_filter):
    suite.addTest(test)

  results = unittest.TextTestRunner(
      verbosity=test_run_options.verbosity,
      resultclass=BrowserTestResult).run(suite)
  if option.write_abbreviated_json_results_to:
    with open(option.write_abbreviated_json_results_to, 'w') as f:
      json_results = {'failures': [], 'successes': [], 'valid': True}
      for (failed_test_case, _) in results.failures:
        json_results['failures'].append(failed_test_case.id())
      for passed_test_case in results.successes:
        json_results['successes'].append(passed_test_case.id())
      json.dump(json_results, f)
  return len(results.failures)
