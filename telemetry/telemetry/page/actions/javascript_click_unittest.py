# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.page.actions import javascript_click
from telemetry.page.actions import wait
from telemetry.unittest import tab_test_case


class ClickElementActionTest(tab_test_case.TabTestCase):
  def testClickWithSelectorWaitForNavigation(self):
    self.Navigate('page_with_link.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'selector': 'a[id="clickme"]'}
    i = javascript_click.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithSingleQuoteSelectorWaitForNavigation(self):
    self.Navigate('page_with_link.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'selector': 'a[id=\'clickme\']'}
    i = javascript_click.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithTextWaitForRefChange(self):
    self.Navigate('page_with_link.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'text': 'Click me'}
    i = javascript_click.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithXPathWaitForRefChange(self):
    self.Navigate('page_with_link.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'xpath': '//a[@id="clickme"]'}
    i = javascript_click.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')
