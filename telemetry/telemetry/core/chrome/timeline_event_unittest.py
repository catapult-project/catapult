# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.chrome import timeline_event

class TimelineEventTest(unittest.TestCase):
  def testChildrenLogic(self):
    # [      top          ]
    #   [ a  ]    [  b  ]
    #    [x]
    top = timeline_event.TimelineEvent('top', 0, 10)
    a = timeline_event.TimelineEvent('a', 1, 2)
    x = timeline_event.TimelineEvent('x', 1.5, 0.25)
    b = timeline_event.TimelineEvent('b', 5, 2)
    top.children.extend([a, b])
    a.children.append(x)

    all_children = top.GetAllChildrenRecursive(include_self=True)
    self.assertEquals([top, a, x, b], all_children)

    self.assertEquals(x.self_time_ms, 0.25)
    self.assertEquals(a.self_time_ms, 1.75) # 2 - 0.25
    self.assertEquals(top.self_time_ms, 6) # 10 - 2 -2

