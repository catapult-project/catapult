# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import tab_test_case
from telemetry import tab_crash_exception
from telemetry import util


def _IsDocumentVisible(tab):
  state = tab.runtime.Evaluate('document.webkitVisibilityState')
  tab.Disconnect()
  return state == 'visible'


class TabTest(tab_test_case.TabTestCase):
  def testNavigateAndWaitToForCompleteState(self):
    self._tab.page.Navigate('http://www.google.com')
    self._tab.WaitForDocumentReadyStateToBeComplete()

  def testNavigateAndWaitToForInteractiveState(self):
    self._tab.page.Navigate('http://www.google.com')
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  def testTabBrowserIsRightBrowser(self):
    self.assertEquals(self._tab.browser, self._browser)

  def testRendererCrash(self):
    self.assertRaises(tab_crash_exception.TabCrashException,
                      lambda: self._tab.page.Navigate('chrome://crash',
                                                      timeout=5))

  def testActivateTab(self):
    self.assertTrue(_IsDocumentVisible(self._tab))
    new_tab = self._browser.tabs.New()
    util.WaitFor(lambda: _IsDocumentVisible(new_tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(self._tab))
    self._tab.Activate()
    util.WaitFor(lambda: _IsDocumentVisible(self._tab), timeout=5)
    self.assertFalse(_IsDocumentVisible(new_tab))

