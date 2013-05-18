# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import os
import sys

from telemetry.core import browser_finder
from telemetry.core import browser_options
from telemetry.page import page_test
from telemetry.page import page_test_results
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
          })

    # We've been given a page set JSON. Load it.
    if page_set_arg.endswith('.json'):
      return page_set.PageSet.FromFile(page_set_arg)

    # We've been given a file or directory. Create a page set containing it.
    if os.path.exists(page_set_arg):
      page_set_dict = {'pages': []}
      if os.path.isdir(page_set_arg):
        for path in os.listdir(page_set_arg):
          path = os.path.join(page_set_arg, path)
          if os.path.isdir(path):
            continue
          print path
          page_set_dict['pages'].append({'url': os.path.join('file://', path)})
      else:
        page_set_dict['pages'].append({'url': 'file://' + page_set_arg})
      return page_set.PageSet.FromDict(page_set_dict)

    raise Exception('Did not understand "%s". Pass a page set, file or URL.' %
                    page_set_arg)

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
    return page_test_results.PageTestResults()

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
    if results.failures:
      logging.warning('Failed pages:\n%s', '\n'.join(zip(*results.failures)[0]))

    if results.errors:
      logging.warning('Errored pages:\n%s', '\n'.join(zip(*results.errors)[0]))

    if results.skipped:
      logging.warning('Skipped pages:\n%s', '\n'.join(zip(*results.skipped)[0]))

    return min(255, len(results.failures + results.errors))

  def PrintParseError(self, message):
    self._parser.error(message)
