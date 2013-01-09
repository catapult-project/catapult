# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline_event import TimelineEvent
from telemetry.timeline_model import TimelineModel

class TimelineModelUnittest(unittest.TestCase):
  def testTimelineEventsOfType(self):
    timeline_model = TimelineModel()
    a = TimelineEvent('a', 0, 10)
    b = TimelineEvent('b', 11, 10)
    timeline_model.AddEvent(a)
    timeline_model.AddEvent(b)
    timeline_model.DidFinishRecording()
    self.assertEquals(1, len(timeline_model.GetAllOfName('a')))
