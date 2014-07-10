# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.core import util
from telemetry.page.actions import loop
from telemetry.unittest import tab_test_case


AUDIO_1_LOOP_CHECK = 'window.__hasEventCompleted("#audio_1", "loop");'
VIDEO_1_LOOP_CHECK = 'window.__hasEventCompleted("#video_1", "loop");'


class LoopActionTest(tab_test_case.TabTestCase):

  def setUp(self):
    tab_test_case.TabTestCase.setUp(self)
    self.Navigate('video_test.html')

  @decorators.Disabled('android')
  def testLoopWithNoSelector(self):
    """Tests that with no selector Loop action loops first media element."""
    action = loop.LoopAction(loop_count=2, selector='#video_1')
    action.WillRunAction(self._tab)
    action.RunAction(self._tab)
    # Assert only first video has played.
    self.assertTrue(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertFalse(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))

  @decorators.Disabled('android')
  def testLoopWithAllSelector(self):
    """Tests that Loop action loops all video elements with selector='all'."""
    action = loop.LoopAction(loop_count=2, selector='all')
    action.WillRunAction(self._tab)
    # Both videos not playing before running action.
    self.assertFalse(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertFalse(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))
    action.RunAction(self._tab)
    # Assert all media elements played.
    self.assertTrue(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertTrue(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))

  @decorators.Disabled('android')
  def testLoopWaitForLoopTimeout(self):
    """Tests that wait_for_loop timeout_in_secondss if video does not loop."""
    action = loop.LoopAction(loop_count=2, selector='#video_1',
                             timeout_in_seconds=1)
    action.WillRunAction(self._tab)
    self.assertFalse(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertRaises(util.TimeoutException, action.RunAction, self._tab)
