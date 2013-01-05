# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import fnmatch
import logging
import os
import traceback
import unittest

from telemetry import browser_options
from telemetry import options_for_unittests

def RequiresBrowserOfType(*types):
  def wrap(func):
    func._requires_browser_types = types
    return func
  return wrap

def Discover(start_dir, pattern = 'test*.py', top_level_dir = None):
  if hasattr(unittest.defaultTestLoader, 'discover'):
    return unittest.defaultTestLoader.discover( # pylint: disable=E1101
      start_dir,
      pattern,
      top_level_dir)

  modules = []
  for dirpath, _, filenames in os.walk(start_dir):
    for filename in filenames:
      if not filename.endswith('.py'):
        continue

      if not fnmatch.fnmatch(filename, pattern):
        continue

      if filename.startswith('.') or filename.startswith('_'):
        continue
      name, _ = os.path.splitext(filename)

      relpath = os.path.relpath(dirpath, top_level_dir)
      fqn = relpath.replace('/', '.') + '.' + name

      # load the module
      try:
        module = __import__(fqn, fromlist=[True])
      except Exception:
        print 'While importing [%s]\n' % fqn
        traceback.print_exc()
        continue
      modules.append(module)

  loader = unittest.defaultTestLoader
  subsuites = []
  for module in modules:
    if hasattr(module, 'suite'):
      new_suite = module.suite()
    else:
      new_suite = loader.loadTestsFromModule(module)
    if new_suite.countTestCases():
      subsuites.append(new_suite)
  return unittest.TestSuite(subsuites)

def FilterSuite(suite, predicate):
  new_suite = unittest.TestSuite()
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

def DiscoverAndRunTests(dir_name, args, top_level_dir):
  suite = Discover(dir_name, '*_unittest.py', top_level_dir)

  def IsTestSelected(test):
    if len(args) != 0:
      found = False
      for name in args:
        if name in test.id():
          found = True
      if not found:
        return False

    if hasattr(test, '_testMethodName'):
      method = getattr(test, test._testMethodName) # pylint: disable=W0212
      if hasattr(method, '_requires_browser_types'):
        types = method._requires_browser_types # pylint: disable=W0212
        if options_for_unittests.GetBrowserType() not in types:
          logging.debug('Skipping test %s because it requires %s' %
                        (test.id(), types))
          return False

    return True

  filtered_suite = FilterSuite(suite, IsTestSelected)
  runner = unittest.TextTestRunner(verbosity = 2)
  test_result = runner.run(filtered_suite)
  return len(test_result.errors) + len(test_result.failures)

def Main(args, start_dir, top_level_dir):
  """Unit test suite that collects all test cases for telemetry."""
  default_options = browser_options.BrowserOptions()
  default_options.browser_type = 'any'

  parser = default_options.CreateParser('run_tests [options] [test names]')
  parser.add_option('--repeat-count', dest='run_test_repeat_count',
                    type='int', default=1,
                    help='Repeats each a provided number of times.')

  _, args = parser.parse_args(args)

  if default_options.verbosity == 0:
    logging.getLogger().setLevel(logging.ERROR)

  from telemetry import browser_finder
  browser_to_create = browser_finder.FindBrowser(default_options)
  if browser_to_create == None:
    logging.error('No browser found of type %s. Cannot run tests.',
                  default_options.browser_type)
    logging.error('Re-run with --browser=list to see available browser types.')
    return 1

  options_for_unittests.Set(default_options,
                            browser_to_create.browser_type)
  olddir = os.getcwd()
  num_errors = 0
  try:
    os.chdir(top_level_dir)
    for _ in range(
        default_options.run_test_repeat_count): # pylint: disable=E1101
      num_errors += DiscoverAndRunTests(start_dir, args, top_level_dir)
  finally:
    os.chdir(olddir)
    options_for_unittests.Set(None, None)

  return min(num_errors, 255)
