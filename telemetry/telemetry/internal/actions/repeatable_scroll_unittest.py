# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.actions import repeatable_scroll
from telemetry.internal.browser import browser_info as browser_info_module
from telemetry.testing import tab_test_case


class RepeatableScrollActionTest(tab_test_case.TabTestCase):

  def setUp(self):
    tab_test_case.TabTestCase.setUp(self)
    self.Navigate('blank.html')

    # Make page bigger than window so it's scrollable.
    self._tab.ExecuteJavaScript('document.body.style.height = '
                                ' (3 * window.innerHeight + 1) + "px";')

    self.assertEquals(
        self._tab.EvaluateJavaScript('document.documentElement.scrollTop '
                                     '|| document.body.scrollTop'), 0)

    self._browser_info = browser_info_module.BrowserInfo(self._tab.browser)
    self._window_height = int(
        self._tab.EvaluateJavaScript('window.innerHeight'))

  def testRepeatableScrollActionNoRepeats(self):
    if not self._browser_info.HasRepeatableSynthesizeScrollGesture():
      return

    expected_scroll = (self._window_height / 2) - 1

    i = repeatable_scroll.RepeatableScrollAction(y_scroll_distance_ratio=0.5)
    i.WillRunAction(self._tab)

    i.RunAction(self._tab)

    scroll_position = self._tab.EvaluateJavaScript(
        '(document.documentElement.scrollTop || document.body.scrollTop)')
    # We can only expect the final scroll position to be approximatly equal.
    self.assertTrue(abs(scroll_position - expected_scroll) < 20,
                    msg='scroll_position=%d;expected %d' % (scroll_position,
                                                            expected_scroll))

  def testRepeatableScrollActionTwoRepeats(self):
    if not self._browser_info.HasRepeatableSynthesizeScrollGesture():
      return

    expected_scroll = ((self._window_height / 2) - 1) * 3

    i = repeatable_scroll.RepeatableScrollAction(y_scroll_distance_ratio=0.5,
                                                 repeat_count=2,
                                                 repeat_delay_ms=1)
    i.WillRunAction(self._tab)

    i.RunAction(self._tab)

    scroll_position = self._tab.EvaluateJavaScript(
        '(document.documentElement.scrollTop || document.body.scrollTop)')
    # We can only expect the final scroll position to be approximatly equal.
    self.assertTrue(abs(scroll_position - expected_scroll) < 20,
                    msg='scroll_position=%d;expected %d' % (scroll_position,
                                                            expected_scroll))
