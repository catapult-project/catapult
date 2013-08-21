# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.page import page as page_module
from telemetry.page.actions import navigate
from telemetry.unittest import tab_test_case


class NavigateActionTest(tab_test_case.TabTestCase):
  def CreatePageFromUnittestDataDir(self, filename):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    return page_module.Page(
        self._browser.http_server.UrlOf(filename),
        None  # In this test, we don't need a page set.
    )

  def testNavigateAction(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())

    page = self.CreatePageFromUnittestDataDir('blank.html')
    i = navigate.NavigateAction()
    i.RunAction(page, self._tab, None)
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')
