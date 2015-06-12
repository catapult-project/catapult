# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from collections import namedtuple
from telemetry.internal.results import page_test_results
from telemetry.page import page
from telemetry.web_perf.metrics import layout
from telemetry.web_perf import timeline_interaction_record

FakeEvent = namedtuple('Event', 'name, start, end')
Interaction = timeline_interaction_record.TimelineInteractionRecord


def GetLayoutMetrics(events, interactions):
  results = page_test_results.PageTestResults()
  results.WillRunPage(page.Page('file://blank.html'))
  layout.LayoutMetric()._AddResultsInternal(events, interactions, results)
  return dict((value.name, value.values) for value in
              results.current_page_run.values)

def FakeLayoutEvent(start, end):
  return FakeEvent(layout.LayoutMetric.EVENT_NAME, start, end)


class LayoutMetricUnitTest(unittest.TestCase):
  def testLayoutMetric(self):
    events = [FakeLayoutEvent(0, 1),
              FakeLayoutEvent(9, 11),
              FakeLayoutEvent(10, 13),
              FakeLayoutEvent(20, 24),
              FakeLayoutEvent(21, 26),
              FakeLayoutEvent(29, 35),
              FakeLayoutEvent(30, 37),
              FakeLayoutEvent(40, 48),
              FakeLayoutEvent(41, 50),
              FakeEvent('something', 10, 13),
              FakeEvent('FrameView::something', 20, 24),
              FakeEvent('SomeThing::performLayout', 30, 37),
              FakeEvent('something else', 40, 48)]
    interactions = [Interaction('interaction', 10, 20),
                    Interaction('interaction', 30, 40)]

    self.assertFalse(GetLayoutMetrics(events, []))
    self.assertFalse(GetLayoutMetrics([], interactions))

    # The first event starts before the first interaction, so it is ignored.
    # The second event starts before the first interaction, so it is ignored.
    # The third event starts during the first interaction, and its duration is
    # 13 - 10 = 3.
    # The fourth event starts during the first interaction, and its duration is
    # 24 - 20 = 4.
    # The fifth event starts between the two interactions, so it is ignored.
    # The sixth event starts between the two interactions, so it is ignored.
    # The seventh event starts during the second interaction, and its duration
    # is 37 - 30 = 7.
    # The eighth event starts during the second interaction, and its duration is
    # 48 - 40 = 8.
    # The ninth event starts after the last interaction, so it is ignored.
    # The rest of the events are not layout events, so they are ignored.
    self.assertEqual({'layout': [3, 4, 7, 8]}, GetLayoutMetrics(
        events, interactions))
