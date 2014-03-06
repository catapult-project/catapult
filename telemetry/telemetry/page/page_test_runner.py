# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from telemetry import test as test_module
from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.page import page_test as page_test_module
from telemetry.page import page_runner
from telemetry.page import page_set

def Main(env):
  """Turns a PageTest into a command-line program.

  Args:
    base_dir: Path to directory containing tests and ProfileCreators.
  """
  runner = PageTestRunner()
  sys.exit(runner.Run(env))

class PageTestRunner(object):
  def __init__(self):
    self._parser = None
    self._options = None
    self._args = None

  @property
  def test_class(self):
    return page_test_module.PageTest

  @property
  def test_class_name(self):
    return 'test'

  def Run(self, env):
    test, ps, expectations = self.ParseCommandLine(sys.argv, env)
    results = page_runner.Run(test, ps, expectations, self._options)
    results.PrintSummary()
    return min(255, len(results.failures + results.errors))

  def FindTestConstructors(self, base_dirs):
    # Look for both Tests and PageTests, but Tests get priority, because
    test_constructors = {}
    for base_dir in base_dirs:
      test_constructors.update(discover.DiscoverClasses(
          base_dir, base_dir, self.test_class))
    for base_dir in base_dirs:
      test_constructors.update(discover.DiscoverClasses(
          base_dir, base_dir, test_module.Test, index_by_class_name=True))
    return test_constructors

  def FindTestName(self, test_constructors, args):
    """Find the test name in an arbitrary argument list.

    We can't use the optparse parser, because the test may add its own
    command-line options. If the user passed in any of those, the
    optparse parsing will fail.

    Returns:
      test_name or None
    """
    test_name = None
    for arg in args:
      if arg in test_constructors:
        test_name = arg

    return test_name

  def GetPageSet(self, test, env):
    ps = test.CreatePageSet(self._args, self._options)
    if ps:
      return ps

    if len(self._args) < 2:
      page_set_filenames = []
      for perf_path in env.base_paths:
        # Check if page_sets subfolder is present, and get all page_sets
        # files if present.
        page_set_dir = os.path.join(perf_path, "page_sets")
        if not os.path.exists(page_set_dir):
          continue
        page_set_filenames.append(
            discover.GetAllPageSetFilenames(page_set_dir))
      page_set_list = ',\n'.join(
          sorted([os.path.relpath(f) for f in page_set_filenames]))
      self.PrintParseError(
          'No page set, file, or URL specified.\n'
          'Available page sets:\n'
          '%s' % page_set_list)

    page_set_arg = self._args[1]

    # We've been given a URL. Create a page set with just that URL.
    if (page_set_arg.startswith('http://') or
        page_set_arg.startswith('https://')):
      self._options.allow_live_sites = True
      return page_set.PageSet.FromDict({
          'pages': [{'url': page_set_arg}]
          }, os.path.dirname(__file__))

    # We've been given a page set JSON. Load it.
    if page_set_arg.endswith('.json'):
      return page_set.PageSet.FromFile(page_set_arg)

    # We've been given a file or directory. Create a page set containing it.
    if os.path.exists(page_set_arg):
      page_set_dict = {'pages': []}

      def _AddFile(file_path):
        page_set_dict['pages'].append({'url': 'file://' + file_path})

      def _AddDir(dir_path):
        for path in os.listdir(dir_path):
          path = os.path.join(dir_path, path)
          _AddPath(path)

      def _AddPath(path):
        if os.path.isdir(path):
          _AddDir(path)
        else:
          _AddFile(path)

      _AddPath(page_set_arg)
      return page_set.PageSet.FromDict(page_set_dict, os.getcwd() + os.sep)

    raise Exception('Did not understand "%s". Pass a page set, file or URL.' %
                    page_set_arg)

  def ParseCommandLine(self, args, env):
    self._options = browser_options.BrowserFinderOptions()
    self._parser = self._options.CreateParser(
        '%%prog [options] %s page_set' % self.test_class_name)

    test_constructors = self.FindTestConstructors(env.base_paths)
    test_name = self.FindTestName(test_constructors, args)
    test = None
    if test_name:
      test = test_constructors[test_name]()
      if isinstance(test, test_module.Test):
        page_test = test.test()
      else:
        page_test = test
      page_test.AddCommandLineOptions(self._parser)
    page_runner.AddCommandLineOptions(self._parser)

    _, self._args = self._parser.parse_args()

    if len(self._args) < 1:
      error_message = 'No %s specified.\nAvailable %ss:\n' % (
          self.test_class_name, self.test_class_name)
      test_list_string = ',\n'.join(sorted(test_constructors.keys()))
      self.PrintParseError(error_message + test_list_string)

    if not test:
      error_message = 'No %s named %s.\nAvailable %ss:\n' % (
          self.test_class_name, self._args[0], self.test_class_name)
      test_list_string = ',\n'.join(sorted(test_constructors.keys()))
      self.PrintParseError(error_message + test_list_string)

    if isinstance(test, test_module.Test):
      ps = test.CreatePageSet(self._options)
      expectations = test.CreateExpectations(ps)
    else:
      ps = self.GetPageSet(test, env)
      expectations = test.CreateExpectations(ps)

    if len(self._args) > 2:
      self.PrintParseError('Too many arguments.')

    return page_test, ps, expectations

  def PrintParseError(self, message):
    self._parser.error(message)
