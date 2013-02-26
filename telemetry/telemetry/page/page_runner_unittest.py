# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import tempfile
import unittest

from telemetry.core import browser_finder
from telemetry.core import user_agent
from telemetry.page import page as page_module
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import page_runner
from telemetry.test import options_for_unittests

SIMPLE_CREDENTIALS_STRING = """
{
  "test": {
    "username": "example",
    "password": "asdf"
  }
}
"""
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
  # page_benchmark_unittest to here.

  def testHandlingOfCrashedTab(self):
    ps = page_set.PageSet()
    page1 = page_module.Page('chrome://crash', ps)
    page2 = page_module.Page('http://www.google.com', ps)
    ps.pages.append(page1)
    ps.pages.append(page2)
    results = page_test.PageTestResults()

    class Test(page_test.PageTest):
      def RunTest(self, *args):
        pass

    with page_runner.PageRunner(ps) as runner:
      options = options_for_unittests.GetCopy()
      possible_browser = browser_finder.FindBrowser(options)
      runner.Run(options, possible_browser, Test('RunTest'), results)
    self.assertEquals(1, len(results.page_successes))
    self.assertEquals(1, len(results.page_failures))

  def testCredentialsWhenLoginFails(self):
    results = page_test.PageTestResults()
    credentials_backend = StubCredentialsBackend(login_return_value=False)
    did_run = self.runCredentialsTest(credentials_backend, results)
    assert credentials_backend.did_get_login == True
    assert credentials_backend.did_get_login_no_longer_needed == False
    assert did_run == False

  def testCredentialsWhenLoginSucceeds(self):
    results = page_test.PageTestResults()
    credentials_backend = StubCredentialsBackend(login_return_value=True)
    did_run = self.runCredentialsTest(credentials_backend, results)
    assert credentials_backend.did_get_login == True
    assert credentials_backend.did_get_login_no_longer_needed == True
    assert did_run

  def runCredentialsTest(self, # pylint: disable=R0201
                         credentials_backend,
                         results):
    ps = page_set.PageSet()
    page = page_module.Page('http://www.google.com', ps)
    page.credentials = "test"
    ps.pages.append(page)

    did_run = [False]

    with tempfile.NamedTemporaryFile() as f:
      f.write(SIMPLE_CREDENTIALS_STRING)
      f.flush()
      ps.credentials_path = f.name

      class TestThatInstallsCredentialsBackend(page_test.PageTest):
        def __init__(self, credentials_backend):
          super(TestThatInstallsCredentialsBackend, self).__init__('RunTest')
          self._credentials_backend = credentials_backend

        def SetUpBrowser(self, browser):
          browser.credentials.AddBackend(self._credentials_backend)

        def RunTest(self, page, tab, results): # pylint: disable=W0613,R0201
          did_run[0] = True

      test = TestThatInstallsCredentialsBackend(credentials_backend)
      with page_runner.PageRunner(ps) as runner:
        options = options_for_unittests.GetCopy()
        possible_browser = browser_finder.FindBrowser(options)
        runner.Run(options, possible_browser, test, results)

    return did_run[0]

  def testUserAgent(self):
    ps = page_set.PageSet()
    page = page_module.Page(
        'file:///' + os.path.join('..', '..', 'unittest_data', 'blank.html'),
        ps,
        base_dir=os.path.dirname(__file__))
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
    with page_runner.PageRunner(ps) as runner:
      options = options_for_unittests.GetCopy()
      possible_browser = browser_finder.FindBrowser(options)
      results = page_test.PageTestResults()
      runner.Run(options, possible_browser, test, results)

    self.assertTrue(hasattr(test, 'hasRun') and test.hasRun)
