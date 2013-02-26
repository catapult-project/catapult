# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys

class Failure(Exception):
  """Exception that can be thrown from PageBenchmark to indicate an
  undesired but designed-for problem."""
  pass

class PageTestResults(object):
  def __init__(self):
    self.page_successes = []
    self.page_failures = []
    self.skipped_pages = []

  def AddSuccess(self, page):
    self.page_successes.append({'page': page})

  def AddFailure(self, page, message, details):
    self.page_failures.append({'page': page,
                               'message': message,
                               'details': details})

  def AddSkippedPage(self, page, message, details):
    self.skipped_pages.append({'page': page,
                               'message': message,
                               'details': details})

class PageTest(object):
  """A class styled on unittest.TestCase for creating page-specific tests."""

  def __init__(self,
               test_method_name,
               action_name_to_run='',
               needs_browser_restart_after_each_run=False):
    self.options = None
    try:
      self._test_method = getattr(self, test_method_name)
    except AttributeError:
      raise ValueError, 'No such method %s.%s' % (
        self.__class_, test_method_name) # pylint: disable=E1101
    self._action_name_to_run = action_name_to_run
    self._needs_browser_restart_after_each_run = (
        needs_browser_restart_after_each_run)

  @property
  def needs_browser_restart_after_each_run(self):
    return self._needs_browser_restart_after_each_run

  def AddCommandLineOptions(self, parser):
    """Override to expose command-line options for this benchmark.

    The provided parser is an optparse.OptionParser instance and accepts all
    normal results. The parsed options are available in Run as
    self.options."""
    pass

  def CustomizeBrowserOptions(self, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  def CustomizeBrowserOptionsForPage(self, page, options):
    """Add options specific to the test and the given page."""
    if not self.CanRunForPage(page):
      return
    action = self.GetAction(page)
    if action:
      action.CustomizeBrowserOptions(options)

  def SetUpBrowser(self, browser):
    """Override to customize the browser right after it has launched."""
    pass

  def CanRunForPage(self, page): #pylint: disable=W0613
    """Override to customize if the test can be ran for the given page."""
    return True

  def WillNavigateToPage(self, page, tab):
    """Override to do operations before the page is navigated."""
    pass

  def DidNavigateToPage(self, page, tab):
    """Override to do operations right after the page is navigated, but before
    any waiting for completion has occurred."""
    pass

  def WillRunAction(self, page, tab, action):
    """Override to do operations before running the action on the page."""
    pass

  def DidRunAction(self, page, tab, action):
    """Override to do operations after running the action on the page."""
    pass

  def Run(self, options, page, tab, results):
    self.options = options
    action = self.GetAction(page)
    if action:
      action.WillRunAction(page, tab)
      self.WillRunAction(page, tab, action)
      action.RunAction(page, tab, None)
      self.DidRunAction(page, tab, action)
    try:
      self._test_method(page, tab, results)
    finally:
      self.options = None

  def GetAction(self, page):
    if not self._action_name_to_run:
      return None
    action_data = getattr(page, self._action_name_to_run)
    from telemetry.page import all_page_actions
    cls = all_page_actions.FindClassWithName(action_data['action'])
    if not cls:
      sys.stderr.write('Could not find action named %s\n' %
                       action_data['action'])
      sys.stderr.write('Check the pageset for a typo and check the error log' +
                       'for possible python loading/compilation errors\n')
      raise Exception('%s not found' % action_data['action'])
    assert cls
    return cls(action_data)

  @property
  def action_name_to_run(self):
    return self._action_name_to_run
