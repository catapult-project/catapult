# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from collections import namedtuple
from telemetry.page import page
from telemetry.results import page_test_results
from telemetry.web_perf.metrics import layout

FakeEvent = namedtuple('Event', 'name, start, end')


class LayoutMetricUnitTest(unittest.TestCase):
  def testAvgStddev(self):
    results = page_test_results.PageTestResults()
    results.WillRunPage(page.Page('file://blank.html'))
    events = map(FakeEvent._make, [(name, 42, 43) for name in
                                   layout.LayoutMetric.EVENTS])
    layout.LayoutMetric()._AddResults(events, results)
    expected = set()
    for name in layout.LayoutMetric.EVENTS.itervalues():
      expected.add((name + '_avg', 1))
      expected.add((name + '_stddev', 0))
    actual = set((value.name, value.value) for value in
                 results.current_page_run.values)
    self.assertEquals(expected, actual)
