# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys

from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.page import page_test
from telemetry.page import page_runner
from telemetry.page import page_set
from telemetry.test import discover

def Main(test_dir, page_set_filenames):
  """Turns a PageTest into a command-line program.

  Args:
    test_dir: Path to directory containing PageTests.
  """
  runner = PageTestRunner()
  sys.exit(runner.Run(test_dir, page_set_filenames))

class PageTestRunner(object):
  def __init__(self):
    self._parser = None
    self._options = None
    self._args = None

  def AddCommandLineOptions(self, parser):
    pass

  @property
  def test_class(self):
    return page_test.PageTest

  @property
  def test_class_name(self):
    return 'test'

  def Run(self, test_dir, page_set_filenames):
    test, ps = self.ParseCommandLine(sys.argv, test_dir, page_set_filenames)
    results = self.PrepareResults(test)
    self.RunTestOnPageSet(test, ps, results)
    return self.OutputResults(results)

  def FindTestConstructors(self, test_dir):
    return discover.DiscoverClasses(
        test_dir, os.path.join(test_dir, '..'), self.test_class)

  def FindTestName(self, test_constructors, args):
    """Find the test name in an arbitrary argument list.

    We can't use the optparse parser, because the test may add its own
    command-line options. If the user passed in any of those, the
    optparse parsing will fail.

    Returns:
      test_name or none
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
    ps = test.CreatePageSet(self._options)
    if ps:
      return ps

    if len(self._args) < 2:
      page_set_list = ',\n'.join(
          sorted([os.path.relpath(f) for f in page_set_filenames]))
      self.PrintParseError(
          'No page set specified.\n'
          'Available page sets:\n'
          '%s' % page_set_list)

    return page_set.PageSet.FromFile(self._args[1])

  def ParseCommandLine(self, args, test_dir, page_set_filenames):
    self._options = browser_options.BrowserOptions()
    self._parser = self._options.CreateParser(
        '%%prog [options] %s page_set' % self.test_class_name)

    self.AddCommandLineOptions(self._parser)
    page_runner.PageRunner.AddCommandLineOptions(self._parser)
    test_constructors = self.FindTestConstructors(test_dir)
    test_name = self.FindTestName(test_constructors, args)
    test = None
    if test_name:
      test = test_constructors[test_name]()
      test.AddCommandLineOptions(self._parser)

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

  def PrepareResults(self, test):  #pylint: disable=W0613
    return page_test.PageTestResults()

  def RunTestOnPageSet(self, test, ps, results):
    test.CustomizeBrowserOptions(self._options)
    possible_browser = browser_finder.FindBrowser(self._options)
    if not possible_browser:
      self.PrintParseError(
          'No browser found.\n'
          'Use --browser=list to figure out which are available.')

    with page_runner.PageRunner(ps) as runner:
      runner.Run(self._options, possible_browser, test, results)

  def OutputResults(self, results):
    if len(results.page_failures):
      logging.warning('Failed pages: %s', '\n'.join(
          [failure['page'].url for failure in results.page_failures]))

    if len(results.skipped_pages):
      logging.warning('Skipped pages: %s', '\n'.join(
          [skipped['page'].url for skipped in results.skipped_pages]))

    return min(255, len(results.page_failures))

  def PrintParseError(self, message):
    self._parser.error(message)
