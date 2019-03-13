# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os

from telemetry.testing import serially_executed_browser_test_case
from telemetry.core import util
from typ import json_results

def ConvertPathToTestName(url):
  return url.replace('.', '_')


class BrowserTest(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases_JavascriptTest(cls, options):
    del options  # unused
    for path in ['page_with_link.html', 'page_with_clickables.html']:
      yield 'add_1_and_2_' + ConvertPathToTestName(path), (path, 1, 2, 3)

  @classmethod
  def SetUpProcess(cls):
    super(cls, BrowserTest).SetUpProcess()
    cls.SetBrowserOptions(cls._finder_options)
    cls.StartBrowser()
    cls.action_runner = cls.browser.tabs[0].action_runner
    cls.SetStaticServerDirs(
        [os.path.join(os.path.abspath(__file__), '..', 'pages')])

  def JavascriptTest(self, file_path, num_1, num_2, expected_sum):
    url = self.UrlOfStaticFilePath(file_path)
    self.action_runner.Navigate(url)
    actual_sum = self.action_runner.EvaluateJavaScript(
        '{{ num_1 }} + {{ num_2 }}', num_1=num_1, num_2=num_2)
    self.assertEquals(expected_sum, actual_sum)

  def TestClickablePage(self):
    url = self.UrlOfStaticFilePath('page_with_clickables.html')
    self.action_runner.Navigate(url)
    self.action_runner.ExecuteJavaScript('valueSettableByTest = 1997')
    self.action_runner.ClickElement(text='Click/tap me')
    self.assertEqual(
        1997, self.action_runner.EvaluateJavaScript('valueToTest'))

  def TestAndroidUI(self):
    if self.platform.GetOSName() != 'android':
      self.skipTest('The test is for android only')
    url = self.UrlOfStaticFilePath('page_with_clickables.html')
    # Nativgate to page_with_clickables.html
    self.action_runner.Navigate(url)
    # Click on history
    self.platform.system_ui.WaitForUiNode(
        resource_id='com.google.android.apps.chrome:id/menu_button')
    self.platform.system_ui.GetUiNode(
        resource_id='com.google.android.apps.chrome:id/menu_button').Tap()
    self.platform.system_ui.WaitForUiNode(content_desc='History')
    self.platform.system_ui.GetUiNode(content_desc='History').Tap()
    # Click on the first entry of the history (page_with_clickables.html)
    self.action_runner.WaitForElement('#id-0')
    self.action_runner.ClickElement('#id-0')
    # Verify that the page's js is interactable
    self.action_runner.WaitForElement(text='Click/tap me')
    self.action_runner.ExecuteJavaScript('valueSettableByTest = 1997')
    self.action_runner.ClickElement(text='Click/tap me')
    self.assertEqual(
        1997, self.action_runner.EvaluateJavaScript('valueToTest'))


class ImplementsGenerateTagsFunction(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTags(cls, finder_options, possible_browser):
    del finder_options, possible_browser
    return ['foo', 'bar']

  @classmethod
  def GenerateTestCases__RunsFailingTest(cls, options):
    del options
    yield 'FailingTest', ()

  def _RunsFailingTest(self):
    assert False


class ImplementsExpectationsFilesFunction(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases__RunsFailingTest(cls, options):
    del options
    yield 'FailingTest', ()

  def _RunsFailingTest(self):
    assert False

  @classmethod
  def ExpectationsFiles(cls):
    return [os.path.join(util.GetTelemetryDir(), 'examples', 'browser_tests',
                         'example_test_expectations.txt')]


class FlakyTest(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):
  _retry_count = 0

  @classmethod
  def GenerateTestCases__RunFlakyTest(cls, options):
    del options  # Unused.
    yield 'RunFlakyTest', ()

  def _RunFlakyTest(self):
    cls = self.__class__
    if cls._retry_count < 3:
      cls._retry_count += 1
      self.fail()
    return


class TestsWillBeDisabled(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases__RunTestThatSkips(cls, options):
    del options
    yield 'ThisTestSkips', ()

  @classmethod
  def GenerateTestCases__RunTestThatSkipsViaCommandLineArg(cls, options):
    del options
    yield 'SupposedToPass', ()

  def _RunTestThatSkipsViaCommandLineArg(self):
    pass

  def _RunTestThatSkips(self):
    self.skipTest('SKIPPING TEST')


class GetsExpectationsFromTyp(
    serially_executed_browser_test_case.SeriallyExecutedBrowserTestCase):

  @classmethod
  def GenerateTestCases__RunsWithExpectationsFile(cls, options):
    del options
    yield 'HasExpectationsFile', ()

  @classmethod
  def GenerateTestCases__RunsWithoutExpectationsFile(cls, options):
    del options
    yield 'HasNoExpectationsFile', ()

  def _RunsWithExpectationsFile(self):
    if (self.GetExpectationsForTest() ==
        (set([json_results.ResultType.Failure]), True)):
      return
    self.fail()

  def _RunsWithoutExpectationsFile(self):
    if (self.GetExpectationsForTest() ==
        (set([json_results.ResultType.Pass]), False)):
      return
    self.fail()


def load_tests(loader, tests, pattern): # pylint: disable=invalid-name
  del loader, tests, pattern  # Unused.
  return serially_executed_browser_test_case.LoadAllTestsInModule(
      sys.modules[__name__])
