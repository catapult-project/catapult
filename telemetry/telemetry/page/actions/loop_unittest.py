# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.page.actions import loop
from telemetry.unittest import tab_test_case
from telemetry.unittest import test

AUDIO_1_LOOP_CHECK = 'window.__hasEventCompleted("#audio_1", "loop");'
VIDEO_1_LOOP_CHECK = 'window.__hasEventCompleted("#video_1", "loop");'


class LoopActionTest(tab_test_case.TabTestCase):

  def setUp(self):
    tab_test_case.TabTestCase.setUp(self)
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self._tab.Navigate(self._browser.http_server.UrlOf('video_test.html'))
    self._tab.WaitForDocumentReadyStateToBeComplete()

  @test.Disabled('chromeos')
  def testLoopWithNoSelector(self):
    """Tests that with no selector Loop action loops first media element."""
    data = {'selector': '#video_1', 'loop_count': 2}
    action = loop.LoopAction(data)
    action.WillRunAction(None, self._tab)
    action.RunAction(None, self._tab, None)
    # Assert only first video has played.
    self.assertTrue(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertFalse(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))

  @test.Disabled('chromeos')
  def testLoopWithAllSelector(self):
    """Tests that Loop action loops all video elements with selector='all'."""
    data = {'selector': 'all', 'loop_count': 2}
    action = loop.LoopAction(data)
    action.WillRunAction(None, self._tab)
    # Both videos not playing before running action.
    self.assertFalse(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertFalse(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))
    action.RunAction(None, self._tab, None)
    # Assert all media elements played.
    self.assertTrue(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertTrue(self._tab.EvaluateJavaScript(AUDIO_1_LOOP_CHECK))

  @test.Disabled('chromeos')
  def testLoopWaitForLoopTimeout(self):
    """Tests that wait_for_loop timeouts if video does not loop."""
    data = {'selector': '#video_1',
            'wait_timeout': 1,
            'loop_count': 2}
    action = loop.LoopAction(data)
    action.WillRunAction(None, self._tab)
    self.assertFalse(self._tab.EvaluateJavaScript(VIDEO_1_LOOP_CHECK))
    self.assertRaises(util.TimeoutException, action.RunAction, None, self._tab,
                      None)

  def testLoopWithoutLoopCount(self):
    """Tests that loop action fails with no loop count."""
    data = {}
    action = loop.LoopAction(data)
    action.WillRunAction(None, self._tab)
    self.assertRaises(AssertionError, action.RunAction, None, self._tab, None)
