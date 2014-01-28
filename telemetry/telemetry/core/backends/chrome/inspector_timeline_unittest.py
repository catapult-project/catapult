# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util
from telemetry.core.backends.chrome import inspector_timeline
from telemetry.unittest import tab_test_case


class InspectorTimelineTabTest(tab_test_case.TabTestCase):
  """Test case that opens a browser and creates and then checks an event."""

  def _WaitForAnimationFrame(self):
    """Wait until the variable window.done is set on the tab."""
    def _IsDone():
      return bool(self._tab.EvaluateJavaScript('window.done'))
    util.WaitFor(_IsDone, 5)

  def testGotTimeline(self):
    # While the timeline is recording, call window.webkitRequestAnimationFrame.
    # This will create a FireAnimationEvent, which can be checked below. See:
    # https://developer.mozilla.org/en/docs/Web/API/window.requestAnimationFrame
    with inspector_timeline.InspectorTimeline.Recorder(self._tab):
      self._tab.ExecuteJavaScript(
          """
          var done = false;
          function sleep(ms) {
            var endTime = (new Date().getTime()) + ms;
            while ((new Date().getTime()) < endTime);
          }
          window.webkitRequestAnimationFrame(function() {
            sleep(10);
            window.done = true;
          });
          """)
      self._WaitForAnimationFrame()

    # There should be at least a FireAnimationFrame record with some duration.
    events = self._tab.timeline_model.GetAllEventsOfName('FireAnimationFrame')
    self.assertTrue(len(events) > 0)
    self.assertTrue(events[0].duration > 0)
