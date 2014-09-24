# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import command_line
from telemetry.page import test_expectations
from telemetry.page.actions import action_runner as action_runner_module


class Failure(Exception):
  """Exception that can be thrown from PageTest to indicate an
  undesired but designed-for problem."""


class TestNotSupportedOnPlatformFailure(Failure):
  """Exception that can be thrown to indicate that a certain feature required
  to run the test is not available on the platform, hardware configuration, or
  browser version."""


class MeasurementFailure(Failure):
  """Exception that can be thrown from MeasurePage to indicate an undesired but
  designed-for problem."""


class PageTest(command_line.Command):
  """A class styled on unittest.TestCase for creating page-specific tests.

  Test should override ValidateAndMeasurePage to perform test
  validation and page measurement as necessary.

     class BodyChildElementMeasurement(PageTest):
       def ValidateAndMeasurePage(self, page, tab, results):
         body_child_count = tab.EvaluateJavaScript(
             'document.body.children.length')
         results.AddValue(scalar.ScalarValue(
             page, 'body_children', 'count', body_child_count))

  The class also provide hooks to add test-specific options. Here is
  an example:

     class BodyChildElementMeasurement(PageTest):
       def AddCommandLineArgs(parser):
         parser.add_option('--element', action='store', default='body')

       def ValidateAndMeasurePage(self, page, tab, results):
         body_child_count = tab.EvaluateJavaScript(
             'document.querySelector('%s').children.length')
         results.AddValue(scalar.ScalarValue(
             page, 'children', 'count', child_count))

  Args:
    action_name_to_run: This is the method name in telemetry.page.Page
        subclasses to run.
    discard_first_run: Discard the first run of this page. This is
        usually used with page_repeat and pageset_repeat options.
    attempts: The number of attempts to run if we encountered
        infrastructure problems (as opposed to test issues), such as
        losing a browser.
    max_failures: The number of page failures allowed before we stop
        running other pages.
    is_action_name_to_run_optional: Determines what to do if
        action_name_to_run is not empty but the page doesn't have that
        action. The page will run (without any action) if
        is_action_name_to_run_optional is True, otherwise the page
        will fail.
  """

  options = {}

  def __init__(self,
               action_name_to_run='',
               needs_browser_restart_after_each_page=False,
               discard_first_result=False,
               clear_cache_before_each_run=False,
               attempts=3,
               max_failures=None,
               is_action_name_to_run_optional=False):
    super(PageTest, self).__init__()

    self.options = None
    if action_name_to_run:
      assert action_name_to_run.startswith('Run') \
          and '_' not in action_name_to_run, \
          ('Wrong way of naming action_name_to_run. By new convention,'
           'action_name_to_run must start with Run- prefix and in CamelCase.')
    self._action_name_to_run = action_name_to_run
    self._needs_browser_restart_after_each_page = (
        needs_browser_restart_after_each_page)
    self._discard_first_result = discard_first_result
    self._clear_cache_before_each_run = clear_cache_before_each_run
    self._close_tabs_before_run = True
    self._attempts = attempts
    self._max_failures = max_failures
    self._is_action_name_to_run_optional = is_action_name_to_run_optional
    assert self._attempts > 0, 'Test attempts must be greater than 0'
    # If the test overrides the TabForPage method, it is considered a multi-tab
    # test.  The main difference between this and a single-tab test is that we
    # do not attempt recovery for the former if a tab or the browser crashes,
    # because we don't know the current state of tabs (how many are open, etc.)
    self.is_multi_tab_test = (self.__class__ is not PageTest and
                              self.TabForPage.__func__ is not
                              self.__class__.__bases__[0].TabForPage.__func__)
    # _exit_requested is set to true when the test requests an early exit.
    self._exit_requested = False

  @classmethod
  def SetArgumentDefaults(cls, parser):
    parser.set_defaults(**cls.options)

  @property
  def discard_first_result(self):
    """When set to True, the first run of the test is discarded.  This is
    useful for cases where it's desirable to have some test resource cached so
    the first run of the test can warm things up. """
    return self._discard_first_result

  @discard_first_result.setter
  def discard_first_result(self, discard):
    self._discard_first_result = discard

  @property
  def clear_cache_before_each_run(self):
    """When set to True, the browser's disk and memory cache will be cleared
    before each run."""
    return self._clear_cache_before_each_run

  @property
  def close_tabs_before_run(self):
    """When set to True, all tabs are closed before running the test for the
    first time."""
    return self._close_tabs_before_run

  @close_tabs_before_run.setter
  def close_tabs_before_run(self, close_tabs):
    self._close_tabs_before_run = close_tabs

  @property
  def attempts(self):
    """Maximum number of times test will be attempted."""
    return self._attempts

  @attempts.setter
  def attempts(self, count):
    assert self._attempts > 0, 'Test attempts must be greater than 0'
    self._attempts = count

  @property
  def max_failures(self):
    """Maximum number of failures allowed for the page set."""
    return self._max_failures

  @max_failures.setter
  def max_failures(self, count):
    self._max_failures = count

  def Run(self, args):
    # Define this method to avoid pylint errors.
    # TODO(dtu): Make this actually run the test with args.page_set.
    pass

  def RestartBrowserBeforeEachPage(self):
    """ Should the browser be restarted for the page?

    This returns true if the test needs to unconditionally restart the
    browser for each page. It may be called before the browser is started.
    """
    return self._needs_browser_restart_after_each_page

  def StopBrowserAfterPage(self, browser, page):  # pylint: disable=W0613
    """Should the browser be stopped after the page is run?

    This is called after a page is run to decide whether the browser needs to
    be stopped to clean up its state. If it is stopped, then it will be
    restarted to run the next page.

    A test that overrides this can look at both the page and the browser to
    decide whether it needs to stop the browser.
    """
    return False

  def CustomizeBrowserOptions(self, options):
    """Override to add test-specific options to the BrowserOptions object"""

  def CustomizeBrowserOptionsForSinglePage(self, page, options):
    """Set options specific to the test and the given page.

    This will be called with the current page when the browser is (re)started.
    Changing options at this point only makes sense if the browser is being
    restarted for each page. Note that if page has a startup_url, the browser
    will always be restarted for each run.
    """
    if page.startup_url:
      options.browser_options.startup_url = page.startup_url

  def WillStartBrowser(self, platform):
    """Override to manipulate the browser environment before it launches."""

  def DidStartBrowser(self, browser):
    """Override to customize the browser right after it has launched."""

  def CanRunForPage(self, page):  # pylint: disable=W0613
    """Override to customize if the test can be ran for the given page."""
    if self._action_name_to_run and not self._is_action_name_to_run_optional:
      return hasattr(page, self._action_name_to_run)
    return True

  def WillRunTest(self, options):
    """Override to do operations before the page set(s) are navigated."""
    self.options = options

  def DidRunTest(self, browser, results): # pylint: disable=W0613
    """Override to do operations after all page set(s) are completed.

    This will occur before the browser is torn down.
    """
    self.options = None

  def WillNavigateToPage(self, page, tab):
    """Override to do operations before the page is navigated, notably Telemetry
    will already have performed the following operations on the browser before
    calling this function:
    * Ensure only one tab is open.
    * Call WaitForDocumentReadyStateToComplete on the tab."""

  def DidNavigateToPage(self, page, tab):
    """Override to do operations right after the page is navigated and after
    all waiting for completion has occurred."""

  def WillRunActions(self, page, tab):
    """Override to do operations before running the actions on the page."""

  def DidRunActions(self, page, tab):
    """Override to do operations after running the actions on the page."""

  def CleanUpAfterPage(self, page, tab):
    """Called after the test run method was run, even if it failed."""

  def CreateExpectations(self, page_set):   # pylint: disable=W0613
    """Override to make this test generate its own expectations instead of
    any that may have been defined in the page set."""
    return test_expectations.TestExpectations()

  def TabForPage(self, page, browser):   # pylint: disable=W0613
    """Override to select a different tab for the page.  For instance, to
    create a new tab for every page, return browser.tabs.New()."""
    return browser.tabs[0]

  def ValidatePageSet(self, page_set):
    """Override to examine the page set before the test run.  Useful for
    example to validate that the pageset can be used with the test."""

  def ValidateAndMeasurePage(self, page, tab, results):
    """Override to check test assertions and perform measurement.

    When adding measurement results, call results.AddValue(...) for
    each result. Raise an exception or add a failure.FailureValue on
    failure. page_test.py also provides several base exception classes
    to use.

    Prefer metric value names that are in accordance with python
    variable style. e.g., metric_name. The name 'url' must not be used.

    Put together:
      def ValidateAndMeasurePage(self, page, tab, results):
        res = tab.EvaluateJavaScript('2+2')
        if res != 4:
          raise Exception('Oh, wow.')
        results.AddValue(scalar.ScalarValue(
            page, 'two_plus_two', 'count', res))

    Args:
      page: A telemetry.page.Page instance.
      tab: A telemetry.core.Tab instance.
      results: A telemetry.results.PageTestResults instance.
    """
    # TODO(chrishenry): Switch to raise NotImplementedError() when
    # subclasses no longer override ValidatePage/MeasurePage.
    self.ValidatePage(page, tab, results)

  def ValidatePage(self, page, tab, results):
    """DEPRECATED: Use ValidateAndMeasurePage instead."""
    self.MeasurePage(page, tab, results)

  def MeasurePage(self, page, tab, results):
    """DEPRECATED: Use ValidateAndMeasurePage instead."""

  def RunPage(self, page, tab, results):
    # Run actions.
    interactive = self.options and self.options.interactive
    action_runner = action_runner_module.ActionRunner(
        tab, skip_waits=page.skip_waits)
    self.WillRunActions(page, tab)
    if interactive:
      action_runner.PauseInteractive()
    else:
      self._RunMethod(page, self._action_name_to_run, action_runner)
    self.DidRunActions(page, tab)

    self.ValidateAndMeasurePage(page, tab, results)

  def _RunMethod(self, page, method_name, action_runner):
    if hasattr(page, method_name):
      run_method = getattr(page, method_name)
      run_method(action_runner)

  def RunNavigateSteps(self, page, tab):
    """Navigates the tab to the page URL attribute.

    Runs the 'navigate_steps' page attribute as a compound action.
    """
    action_runner = action_runner_module.ActionRunner(
        tab, skip_waits=page.skip_waits)
    page.RunNavigateSteps(action_runner)

  def IsExiting(self):
    return self._exit_requested

  def RequestExit(self):
    self._exit_requested = True

  @property
  def action_name_to_run(self):
    return self._action_name_to_run
