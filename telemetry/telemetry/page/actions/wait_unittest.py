# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.page.actions import wait
from telemetry.unittest import tab_test_case
from telemetry.unittest import simple_mock


class WaitActionTest(tab_test_case.TabTestCase):
  def testWaitAction(self):
    self.Navigate('blank.html')
    self.assertEquals(
        self._tab.EvaluateJavaScript('document.location.pathname;'),
        '/blank.html')

    mock_timer = simple_mock.MockTimer()
    real_time_sleep = wait.time.sleep
    wait.time.sleep = mock_timer.Sleep

    try:
      i = wait.WaitAction({ 'condition': 'duration', 'seconds': 1 })

      i.RunAction(None, self._tab)
      self.assertEqual(mock_timer.GetTime(), 1)
    finally:
      wait.time.sleep = real_time_sleep

  def testWaitActionTimeout(self):
    mock_timer = simple_mock.MockTimer()
    real_wait_time_sleep = wait.time.sleep
    real_util_time_sleep = util.time.sleep
    real_util_time_time = util.time.time

    wait.time.sleep = mock_timer.Sleep
    util.time.sleep = mock_timer.Sleep
    util.time.time = mock_timer.GetTime

    try:
      wait_action = wait.WaitAction({
        'condition': 'javascript',
        'javascript': '1 + 1 === 3',
        'timeout': 1
      })

      self.assertRaises(
          util.TimeoutException,
          lambda: wait_action.RunAction(None, self._tab))
      self.assertLess(mock_timer.GetTime(), 5)
    finally:
      wait.time.sleep = real_wait_time_sleep
      util.time.sleep = real_util_time_sleep
      util.time.time = real_util_time_time
