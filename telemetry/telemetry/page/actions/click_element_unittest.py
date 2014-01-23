# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.page.actions import click_element
from telemetry.page.actions import wait
from telemetry.unittest import tab_test_case

class ClickElementActionTest(tab_test_case.TabTestCase):
  def testClickWithSelectorWaitForNavigation(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'selector': 'a[id="clickme"]'}
    i = click_element.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithSingleQuoteSelectorWaitForNavigation(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'selector': 'a[id=\'clickme\']'}
    i = click_element.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithTextWaitForRefChange(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'text': 'Click me'}
    i = click_element.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

  def testClickWithXPathWaitForRefChange(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(
      self._browser.http_server.UrlOf('page_with_link.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/page_with_link.html')

    data = {'xpath': '//a[@id="clickme"]'}
    i = click_element.ClickElementAction(data)
    data = {'condition': 'href_change'}
    j = wait.WaitAction(data)
    j.RunAction(None, self._tab, i)

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')
