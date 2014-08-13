# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.page.actions import scroll
from telemetry.unittest import tab_test_case
from telemetry.unittest import test


class ScrollActionTest(tab_test_case.TabTestCase):
  @test.Disabled  # Disabled due to flakiness: crbug.com/330544
  def testScrollAction(self):
    self.Navigate('blank.html')

    # Make page bigger than window so it's scrollable.
    self._tab.ExecuteJavaScript("""document.body.style.height =
                              (2 * window.innerHeight + 1) + 'px';""")

    self.assertEquals(
        self._tab.EvaluateJavaScript("""document.documentElement.scrollTop
                                   || document.body.scrollTop"""), 0)

    i = scroll.ScrollAction()
    i.WillRunAction(self._tab)

    self._tab.ExecuteJavaScript("""
        window.__scrollAction.beginMeasuringHook = function() {
            window.__didBeginMeasuring = true;
        };
        window.__scrollAction.endMeasuringHook = function() {
            window.__didEndMeasuring = true;
        };""")
    i.RunAction(self._tab)

    self.assertTrue(self._tab.EvaluateJavaScript('window.__didBeginMeasuring'))
    self.assertTrue(self._tab.EvaluateJavaScript('window.__didEndMeasuring'))

    # Allow for roundoff error in scaled viewport.
    scroll_position = self._tab.EvaluateJavaScript(
        """(document.documentElement.scrollTop || document.body.scrollTop)
        + window.innerHeight""")
    scroll_height = self._tab.EvaluateJavaScript('document.body.scrollHeight')
    difference = scroll_position - scroll_height
    self.assertTrue(abs(difference) <= 1,
                    msg='scroll_position=%d; scroll_height=%d' %
                            (scroll_position, scroll_height))

  def testBoundingClientRect(self):
    self.Navigate('blank.html')

    with open(os.path.join(os.path.dirname(__file__),
                           'gesture_common.js')) as f:
      js = f.read()
      self._tab.ExecuteJavaScript(js)

    # Verify that the rect returned by getBoundingVisibleRect() in scroll.js is
    # completely contained within the viewport. Scroll events dispatched by the
    # scrolling API use the center of this rect as their location, and this
    # location needs to be within the viewport bounds to correctly decide
    # between main-thread and impl-thread scroll. If the scrollable area were
    # not clipped to the viewport bounds, then the instance used here (the
    # scrollable area being more than twice as tall as the viewport) would
    # result in a scroll location outside of the viewport bounds.
    self._tab.ExecuteJavaScript("""document.body.style.height =
                           (3 * window.innerHeight + 1) + 'px';""")
    self._tab.ExecuteJavaScript("""document.body.style.width =
                           (3 * window.innerWidth + 1) + 'px';""")
    self._tab.ExecuteJavaScript(
        "window.scrollTo(window.innerWidth, window.innerHeight);")

    rect_top = int(self._tab.EvaluateJavaScript(
        '__GestureCommon_GetBoundingVisibleRect(document.body).top'))
    rect_height = int(self._tab.EvaluateJavaScript(
        '__GestureCommon_GetBoundingVisibleRect(document.body).height'))
    rect_bottom = rect_top + rect_height

    rect_left = int(self._tab.EvaluateJavaScript(
        '__GestureCommon_GetBoundingVisibleRect(document.body).left'))
    rect_width = int(self._tab.EvaluateJavaScript(
        '__GestureCommon_GetBoundingVisibleRect(document.body).width'))
    rect_right = rect_left + rect_width

    viewport_height = int(self._tab.EvaluateJavaScript('window.innerHeight'))
    viewport_width = int(self._tab.EvaluateJavaScript('window.innerWidth'))

    self.assertTrue(rect_top >= 0,
        msg='%s >= %s' % (rect_top, 0))
    self.assertTrue(rect_left >= 0,
        msg='%s >= %s' % (rect_left, 0))
    self.assertTrue(rect_bottom <= viewport_height,
        msg='%s + %s <= %s' % (rect_top, rect_height, viewport_height))
    self.assertTrue(rect_right <= viewport_width,
        msg='%s + %s <= %s' % (rect_left, rect_width, viewport_width))
