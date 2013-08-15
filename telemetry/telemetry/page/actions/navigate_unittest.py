# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page import page as page_module
from telemetry.page.actions import navigate
from telemetry.unittest import tab_test_case


class NavigateActionTest(tab_test_case.TabTestCase):
  def CreatePageFromUnittestDataDir(self, filename):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     os.pardir, os.pardir, os.pardir,
                                     'unittest_data')
    self._browser.SetHTTPServerDirectories(unittest_data_dir)
    return page_module.Page(
        self._browser.http_server.UrlOf(filename),
        None  # In this test, we don't need a page set.
    )

  def testNavigateAction(self):
    unittest_data_dir = os.path.join(os.path.dirname(__file__),
                                     os.pardir, os.pardir, os.pardir,
                                     'unittest_data')
    self._browser.SetHTTPServerDirectories(unittest_data_dir)

    page = self.CreatePageFromUnittestDataDir('blank.html')
    i = navigate.NavigateAction()
    i.RunAction(page, self._tab, None)
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')
