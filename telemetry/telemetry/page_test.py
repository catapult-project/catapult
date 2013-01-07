# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class Failure(Exception):
  """Exception that can be thrown from MultiPageBenchmark to indicate an
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

  def __init__(self, test_method_name, interaction_name_to_run=''):
    self.options = None
    try:
      self._test_method = getattr(self, test_method_name)
    except AttributeError:
      raise ValueError, 'No such method %s.%s' % (
        self.__class_, test_method_name) # pylint: disable=E1101
    self._interaction_name_to_run = interaction_name_to_run

  def AddCommandLineOptions(self, parser):
    """Override to expose command-line options for this benchmark.

    The provided parser is an optparse.OptionParser instance and accepts all
    normal results. The parsed options are available in MeasurePage as
    self.options."""
    pass

  def CustomizeBrowserOptions(self, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  def CustomizeBrowserOptionsForPage(self, page, options):
    """Add options specific to the test and the given page."""
    if not self.CanRunForPage(page):
      return
    interaction = self.GetInteraction(page)
    if interaction:
      interaction.CustomizeBrowserOptions(options)

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

  def WillRunInteraction(self, page, tab):
    """Override to do operations before running the interaction on the page."""
    pass

  def DidRunInteraction(self, page, tab):
    """Override to do operations after running the interaction on the page."""
    pass

  def Run(self, options, page, tab, results):
    self.options = options
    interaction = self.GetInteraction(page)
    if interaction:
      tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()
      self.WillRunInteraction(page, tab)
      interaction.PerformInteraction(page, tab)
      self.DidRunInteraction(page, tab)
    try:
      self._test_method(page, tab, results)
    finally:
      self.options = None

  def GetInteraction(self, page):
    if not self._interaction_name_to_run:
      return None
    interaction_data = getattr(page, self._interaction_name_to_run)
    from telemetry import all_page_interactions
    return all_page_interactions.FindClassWithName(
        interaction_data['action'])(interaction_data)

  @property
  def interaction_name_to_run(self):
    return self._interaction_name_to_run
