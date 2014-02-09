# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.core import util
from telemetry.page.actions import wait
from telemetry.unittest import tab_test_case
from telemetry.unittest import test


class WaitActionTest(tab_test_case.TabTestCase):
  @test.Disabled('chromeos')
  def testWaitAction(self):
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(
      self._browser.http_server.UrlOf('blank.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

    i = wait.WaitAction({ 'condition': 'duration', 'seconds': 1 })

    start_time = time.time()
    i.RunAction(None, self._tab, None)
    self.assertTrue(time.time() - start_time >= 1.0)

  def testWaitActionTimeout(self):
    wait_action = wait.WaitAction({
      'condition': 'javascript',
      'javascript': '1 + 1 === 3',
      'timeout': 1
    })

    start_time = time.time()
    self.assertRaises(
        util.TimeoutException,
        lambda: wait_action.RunAction(None, self._tab, None))
    self.assertTrue(time.time() - start_time < 5)
