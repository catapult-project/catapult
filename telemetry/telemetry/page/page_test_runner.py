# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from telemetry.core import browser_options
from telemetry.core import discover
from telemetry.core import profile_types
from telemetry.page import page_test
from telemetry.page import page_runner
from telemetry.page import page_set

def Main(test_dir, profile_creators_dir, page_set_filenames):
  """Turns a PageTest into a command-line program.

  Args:
    test_dir: Path to directory containing PageTests.
    profile_creators_dir: Path to a directory containing ProfileCreators
  """
  runner = PageTestRunner()
  sys.exit(runner.Run(test_dir, profile_creators_dir, page_set_filenames))

class PageTestRunner(object):
  def __init__(self):
    self._parser = None
    self._options = None
    self._args = None

  @property
  def test_class(self):
    return page_test.PageTest

  @property
  def test_class_name(self):
    return 'test'

  def Run(self, test_dir, profile_creators_dir, page_set_filenames):
    test, ps = self.ParseCommandLine(
        sys.argv, test_dir, profile_creators_dir, page_set_filenames)
    results = page_runner.Run(test, ps, self._options)
    results.PrintSummary()
    return min(255, len(results.failures + results.errors))

  def FindTestConstructors(self, test_dir):
    return discover.DiscoverClasses(
        test_dir, os.path.join(test_dir, '..'), self.test_class)

  def FindTestName(self, test_constructors, args):
    """Find the test name in an arbitrary argument list.

    We can't use the optparse parser, because the test may add its own
    command-line options. If the user passed in any of those, the
    optparse parsing will fail.

    Returns:
      test_name or None
    """
    test_name = None
    for arg in [self.GetModernizedTestName(a) for a in args]:
      if arg in test_constructors:
        test_name = arg

    return test_name

  def GetModernizedTestName(self, arg):
    """Sometimes tests change names but buildbots keep calling the old name.

    If arg matches an old test name, return the new test name instead.
    Otherwise, return the arg.
    """
    return arg

  def GetPageSet(self, test, page_set_filenames):
    ps = test.CreatePageSet(self._args, self._options)
    if ps:
      return ps

    if len(self._args) < 2:
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

  def ParseCommandLine(self, args, test_dir, profile_creators_dir,
      page_set_filenames):
    # Need to collect profile creators before creating command line parser.
    if profile_creators_dir:
      profile_types.FindProfileCreators(profile_creators_dir)

    self._options = browser_options.BrowserOptions()
    self._parser = self._options.CreateParser(
        '%%prog [options] %s page_set' % self.test_class_name)

    test_constructors = self.FindTestConstructors(test_dir)
    test_name = self.FindTestName(test_constructors, args)
    test = None
    if test_name:
      test = test_constructors[test_name]()
      test.AddOutputOptions(self._parser)
      test.AddCommandLineOptions(self._parser)
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

    ps = self.GetPageSet(test, page_set_filenames)

    if len(self._args) > 2:
      self.PrintParseError('Too many arguments.')

    return test, ps

  def PrintParseError(self, message):
    self._parser.error(message)
