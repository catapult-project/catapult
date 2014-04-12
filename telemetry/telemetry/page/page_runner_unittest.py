# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile
import unittest

from telemetry.core import browser_finder
from telemetry.core import exceptions
from telemetry.core import user_agent
from telemetry.core import util
from telemetry.page import page as page_module
from telemetry.page import page_measurement
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import page_runner
from telemetry.page import test_expectations
from telemetry.unittest import options_for_unittests


SIMPLE_CREDENTIALS_STRING = """
{
  "test": {
    "username": "example",
    "password": "asdf"
  }
}
"""


def SetUpPageRunnerArguments(options):
  parser = options.CreateParser()
  page_runner.AddCommandLineArgs(parser)
  options.MergeDefaultValues(parser.get_default_values())
  page_runner.ProcessCommandLineArgs(parser, options)


class StubCredentialsBackend(object):
  def __init__(self, login_return_value):
    self.did_get_login = False
    self.did_get_login_no_longer_needed = False
    self.login_return_value = login_return_value

  @property
  def credentials_type(self): # pylint: disable=R0201
    return 'test'

  def LoginNeeded(self, tab, config): # pylint: disable=W0613
    self.did_get_login = True
    return self.login_return_value

  def LoginNoLongerNeeded(self, tab): # pylint: disable=W0613
    self.did_get_login_no_longer_needed = True


class PageRunnerTests(unittest.TestCase):
  # TODO(nduca): Move the basic "test failed, test succeeded" tests from
  # page_measurement_unittest to here.

  def testHandlingOfCrashedTab(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page1 = page_module.Page('chrome://crash', ps)
    ps.pages.append(page1)

    class Test(page_test.PageTest):
      def RunTest(self, *args):
        pass

    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(Test('RunTest'), ps, expectations, options)
    self.assertEquals(0, len(results.successes))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(1, len(results.errors))

  def testHandlingOfTestThatRaisesWithNonFatalUnknownExceptions(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))

    class ExpectedException(Exception):
      pass

    class Test(page_test.PageTest):
      def __init__(self, *args):
        super(Test, self).__init__(*args)
        self.run_count = 0
      def RunTest(self, *_):
        old_run_count = self.run_count
        self.run_count += 1
        if old_run_count == 0:
          raise ExpectedException()

    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    test = Test('RunTest')
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(test, ps, expectations, options)
    self.assertEquals(2, test.run_count)
    self.assertEquals(1, len(results.successes))
    self.assertEquals(1, len(results.failures))

  def testHandlingOfCrashedTabWithExpectedFailure(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    expectations.Fail('chrome://crash')
    page1 = page_module.Page('chrome://crash', ps)
    ps.pages.append(page1)

    class Test(page_test.PageTest):
      def RunTest(self, *_):
        pass

    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(
        Test('RunTest'), ps, expectations, options)
    self.assertEquals(1, len(results.successes))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(0, len(results.errors))

  def testRetryOnBrowserCrash(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))

    class CrashyMeasurement(page_measurement.PageMeasurement):
      has_crashed = False
      def MeasurePage(self, *_):
        if not self.has_crashed:
          self.has_crashed = True
          raise exceptions.BrowserGoneException()

    options = options_for_unittests.GetCopy()
    options.output_format = 'csv'

    SetUpPageRunnerArguments(options)
    results = page_runner.Run(CrashyMeasurement(), ps, expectations, options)

    self.assertEquals(1, len(results.successes))
    self.assertEquals(0, len(results.failures))
    self.assertEquals(0, len(results.errors))

  def testDiscardFirstResult(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))

    class Measurement(page_measurement.PageMeasurement):
      @property
      def discard_first_result(self):
        return True
      def MeasurePage(self, *args):
        pass

    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    options.reset_results = None
    options.upload_results = None
    options.results_label = None

    options.page_repeat = 1
    options.pageset_repeat = 1
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(Measurement(), ps, expectations, options)
    self.assertEquals(0, len(results.successes))
    self.assertEquals(0, len(results.failures))

    options.page_repeat = 1
    options.pageset_repeat = 2
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(Measurement(), ps, expectations, options)
    self.assertEquals(2, len(results.successes))
    self.assertEquals(0, len(results.failures))

    options.page_repeat = 2
    options.pageset_repeat = 1
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(Measurement(), ps, expectations, options)
    self.assertEquals(2, len(results.successes))
    self.assertEquals(0, len(results.failures))

    options.output_format = 'html'
    options.page_repeat = 1
    options.pageset_repeat = 1
    SetUpPageRunnerArguments(options)
    results = page_runner.Run(Measurement(), ps, expectations, options)
    self.assertEquals(0, len(results.successes))
    self.assertEquals(0, len(results.failures))

  def testPagesetRepeat(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    ps.pages.append(page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir()))
    ps.pages.append(page_module.Page(
        'file://green_rect.html', ps, base_dir=util.GetUnittestDataDir()))

    class Measurement(page_measurement.PageMeasurement):
      i = 0
      def MeasurePage(self, _, __, results):
        self.i += 1
        results.Add('metric', 'unit', self.i)

    output_file = tempfile.NamedTemporaryFile(delete=False).name
    try:
      options = options_for_unittests.GetCopy()
      options.output_format = 'buildbot'
      options.output_file = output_file
      options.reset_results = None
      options.upload_results = None
      options.results_label = None

      options.page_repeat = 1
      options.pageset_repeat = 2
      SetUpPageRunnerArguments(options)
      results = page_runner.Run(Measurement(), ps, expectations, options)
      results.PrintSummary()
      self.assertEquals(4, len(results.successes))
      self.assertEquals(0, len(results.failures))
      stdout = open(output_file).read()
      self.assertIn('RESULT metric_by_url: blank.html= [1,3] unit', stdout)
      self.assertIn('RESULT metric_by_url: green_rect.html= [2,4] unit', stdout)
      self.assertIn('*RESULT metric: metric= [1,2,3,4] unit', stdout)
    finally:
      results._output_stream.close()  # pylint: disable=W0212
      os.remove(output_file)

  def testCredentialsWhenLoginFails(self):
    credentials_backend = StubCredentialsBackend(login_return_value=False)
    did_run = self.runCredentialsTest(credentials_backend)
    assert credentials_backend.did_get_login == True
    assert credentials_backend.did_get_login_no_longer_needed == False
    assert did_run == False

  def testCredentialsWhenLoginSucceeds(self):
    credentials_backend = StubCredentialsBackend(login_return_value=True)
    did_run = self.runCredentialsTest(credentials_backend)
    assert credentials_backend.did_get_login == True
    assert credentials_backend.did_get_login_no_longer_needed == True
    assert did_run

  def runCredentialsTest(self, # pylint: disable=R0201
                         credentials_backend):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    page.credentials = "test"
    ps.pages.append(page)

    did_run = [False]

    try:
      with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(SIMPLE_CREDENTIALS_STRING)
        ps.credentials_path = f.name

      class TestThatInstallsCredentialsBackend(page_test.PageTest):
        def __init__(self, credentials_backend):
          super(TestThatInstallsCredentialsBackend, self).__init__('RunTest')
          self._credentials_backend = credentials_backend

        def DidStartBrowser(self, browser):
          browser.credentials.AddBackend(self._credentials_backend)

        def RunTest(self, page, tab, results): # pylint: disable=W0613,R0201
          did_run[0] = True

      test = TestThatInstallsCredentialsBackend(credentials_backend)
      options = options_for_unittests.GetCopy()
      options.output_format = 'none'
      SetUpPageRunnerArguments(options)
      page_runner.Run(test, ps, expectations, options)
    finally:
      os.remove(f.name)

    return did_run[0]

  def testUserAgent(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    ps.pages.append(page)
    ps.user_agent_type = 'tablet'

    class TestUserAgent(page_test.PageTest):
      def RunTest(self, page, tab, results): # pylint: disable=W0613,R0201
        actual_user_agent = tab.EvaluateJavaScript('window.navigator.userAgent')
        expected_user_agent = user_agent.UA_TYPE_MAPPING['tablet']
        assert actual_user_agent.strip() == expected_user_agent

        # This is so we can check later that the test actually made it into this
        # function. Previously it was timing out before even getting here, which
        # should fail, but since it skipped all the asserts, it slipped by.
        self.hasRun = True # pylint: disable=W0201

    test = TestUserAgent('RunTest')
    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    page_runner.Run(test, ps, expectations, options)

    self.assertTrue(hasattr(test, 'hasRun') and test.hasRun)

  # Ensure that page_runner forces exactly 1 tab before running a page.
  def testOneTab(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    ps.pages.append(page)

    class TestOneTab(page_test.PageTest):
      def __init__(self,
                   test_method_name,
                   action_name_to_run='',
                   needs_browser_restart_after_each_page=False):
        super(TestOneTab, self).__init__(test_method_name, action_name_to_run,
                                         needs_browser_restart_after_each_page)
        self._browser = None

      def DidStartBrowser(self, browser):
        self._browser = browser
        if self._browser.supports_tab_control:
          self._browser.tabs.New()

      def RunTest(self, page, tab, results): # pylint: disable=W0613,R0201
        if not self._browser.supports_tab_control:
          logging.warning('Browser does not support tab control, skipping test')
          return
        assert len(self._browser.tabs) == 1

    test = TestOneTab('RunTest')
    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    page_runner.Run(test, ps, expectations, options)

  # Ensure that page_runner allows the test to customize the browser before it
  # launches.
  def testBrowserBeforeLaunch(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    ps.pages.append(page)

    class TestBeforeLaunch(page_test.PageTest):
      def __init__(self,
                   test_method_name,
                   action_name_to_run=''):
        super(TestBeforeLaunch, self).__init__(
            test_method_name, action_name_to_run, False)
        self._did_call_will_start = False
        self._did_call_did_start = False

      def WillStartBrowser(self, browser):
        self._did_call_will_start = True
        # TODO(simonjam): Test that the profile is available.

      def DidStartBrowser(self, browser):
        assert self._did_call_will_start
        self._did_call_did_start = True

      def RunTest(self, page, tab, results): # pylint: disable=W0613,R0201
        assert self._did_call_did_start

    test = TestBeforeLaunch('RunTest')
    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    page_runner.Run(test, ps, expectations, options)

  def testRunPageWithStartupUrl(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    page.startup_url = 'about:blank'
    ps.pages.append(page)

    class Measurement(page_measurement.PageMeasurement):
      def __init__(self):
        super(Measurement, self).__init__()
        self.browser_restarted = False

      def CustomizeBrowserOptionsForSinglePage(self, ps, options):
        self.browser_restarted = True
        super(Measurement, self).CustomizeBrowserOptionsForSinglePage(ps,
                                                                      options)
      def MeasurePage(self, page, tab, results):
        pass

    options = options_for_unittests.GetCopy()
    options.page_repeat = 2
    options.output_format = 'none'
    if not browser_finder.FindBrowser(options):
      return
    test = Measurement()
    SetUpPageRunnerArguments(options)
    page_runner.Run(test, ps, expectations, options)
    self.assertEquals('about:blank', options.browser_options.startup_url)
    self.assertTrue(test.browser_restarted)

  # Ensure that page_runner calls cleanUp when a page run fails.
  def testCleanUpPage(self):
    ps = page_set.PageSet()
    expectations = test_expectations.TestExpectations()
    page = page_module.Page(
        'file://blank.html', ps, base_dir=util.GetUnittestDataDir())
    ps.pages.append(page)

    class Test(page_test.PageTest):
      def __init__(self,
                   test_method_name,
                   action_name_to_run=''):
        super(Test, self).__init__(
            test_method_name, action_name_to_run, False)
        self.did_call_clean_up = False

      def RunTest(self, _, _2, _3):
        raise Exception('Intentional failure')

      def CleanUpAfterPage(self, page, tab):
        self.did_call_clean_up = True


    test = Test('RunTest')
    options = options_for_unittests.GetCopy()
    options.output_format = 'none'
    SetUpPageRunnerArguments(options)
    page_runner.Run(test, ps, expectations, options)
    assert test.did_call_clean_up
