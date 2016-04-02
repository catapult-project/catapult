# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page import action_runner
from telemetry.testing import serially_executed_browser_test_case


def ConvertPathToTestName(url):
  return url.replace('.', '_')


class SimpleJavascriptTest(
    serially_executed_browser_test_case.SeriallyBrowserTestCase):

  @classmethod
  def GenerateTestCases_TestJavascript(cls, options):
    del options  # unused
    for path in ['page_with_link.html', 'page_with_clickables.html']:
      yield 'add_1_and_2_' + ConvertPathToTestName(path), (path, 1, 2, 3)

  @classmethod
  def setUpClass(cls):
    super(cls, SimpleJavascriptTest).setUpClass()
    cls.action_runner = action_runner.ActionRunner(cls._browser.tabs[0])
    cls.SetStaticServerDir(
        os.path.join(os.path.abspath(__file__), '..', 'pages'))

  def TestJavascript(self, file_path, num_1, num_2, expected_sum):
    url = self.UrlOfStaticFilePath(file_path)
    self.action_runner.Navigate(url)
    actual_sum = self.action_runner.EvaluateJavaScript(
        '%i + %i' % (num_1, num_2))
    self.assertEquals(expected_sum, actual_sum)

  def testClickablePage(self):
    url = self.UrlOfStaticFilePath('page_with_clickables.html')
    self.action_runner.Navigate(url)
    self.action_runner.ExecuteJavaScript('valueSettableByTest = 1997')
    self.action_runner.ClickElement(text='Click/tap me')
    self.assertEqual(1997, self.action_runner.EvaluateJavaScript('valueToTest'))
