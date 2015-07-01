# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import util
from telemetry.internal.results import page_test_results
from telemetry.page import page
from telemetry.web_perf.metrics import memory_timeline
from telemetry.web_perf import timeline_interaction_record

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'mock')
import mock # pylint: disable=import-error


def MockMemoryDump(start, end, stats):
  memory_dump = mock.Mock()
  memory_dump.start = start
  memory_dump.end = end
  memory_dump.has_mmaps = stats is not None
  # As a shortcut, if stats are given as a single int value, we create a dict
  # with all metrics mapping to that same value.
  if stats is None or isinstance(stats, int):
    stats = dict.fromkeys(memory_timeline.REPORTED_METRICS, stats or 0)
  memory_dump.GetStatsSummary = mock.Mock(return_value=stats)
  return memory_dump


def TestInteraction(start, end):
  return timeline_interaction_record.TimelineInteractionRecord(
      'Action_TestInteraction', start, end)


class MemoryTimelineMetricUnitTest(unittest.TestCase):
  def getResultsDict(self, events, interactions):
    def strip_prefix(key, prefix):
      self.assertTrue(key.startswith(prefix))
      return key[len(prefix):]

    results = page_test_results.PageTestResults()
    test_page = page.Page('http://google.com')
    results.WillRunPage(test_page)
    metric = memory_timeline.MemoryTimelineMetric()
    mock_model = mock.Mock()
    mock_model.IterMemoryDumpEvents = mock.Mock(return_value=events)
    metric.AddResults(mock_model, None, interactions, results)
    result_dict = {strip_prefix(v.name, 'memory_'): v.values
                   for v in results.current_page_run.values}
    results.DidRunPage(test_page)
    # REPORTED_METRICS are exactly the ones reported
    self.assertItemsEqual(memory_timeline.REPORTED_METRICS,
                          result_dict.keys())
    return result_dict

  def getMetricValues(self, events, interactions):
    result_dict = self.getResultsDict(events, interactions)
    # values for all metrics should be identical in this case
    values = result_dict.popitem()[1]
    for other_values in result_dict.itervalues():
      self.assertEquals(values, other_values)
    return values

  def testSingleMemoryDump(self):
    events = [MockMemoryDump(2, 4, 123)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123],
                      self.getMetricValues(events, interactions))

  def testMultipleMemoryDumps(self):
    events = [MockMemoryDump(2, 4, 123),
              MockMemoryDump(5, 6, 456)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123, 456],
                      self.getMetricValues(events, interactions))

  def testMultipleInteractions(self):
    events = [MockMemoryDump(2, 4, 123),
              MockMemoryDump(5, 6, 456),
              MockMemoryDump(13, 14, 789)]
    interactions = [TestInteraction(1, 10),
                    TestInteraction(12, 15)]
    self.assertEquals([123, 456, 789],
                      self.getMetricValues(events, interactions))

  def testDumpsOutsideSingleInteractionAreFilteredOut(self):
    events = [MockMemoryDump(0, 1, 555),
              MockMemoryDump(2, 4, 123),
              MockMemoryDump(5, 6, 456),
              MockMemoryDump(8, 11, 789)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123, 456],
                      self.getMetricValues(events, interactions))

  def testDumpsOutsideMultipleInteractionsAreFilteredOut(self):
    events = [MockMemoryDump(0, 1, 111),
              MockMemoryDump(2, 4, 123),
              MockMemoryDump(11, 12, 456),
              MockMemoryDump(13, 14, 555),
              MockMemoryDump(11, 12, 789)]
    interactions = [TestInteraction(1, 10),
                    TestInteraction(12, 15)]
    self.assertEquals([123, 555],
                      self.getMetricValues(events, interactions))

  def testDumpsWithNoMemoryMapsAreFilteredOut(self):
    events = [MockMemoryDump(2, 4, 123),
              MockMemoryDump(5, 6, None)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123],
                      self.getMetricValues(events, interactions))

  def testReturnsNoneWhenAllDumpsAreFilteredOut(self):
    events = [MockMemoryDump(0, 1, 555),
              MockMemoryDump(8, 11, 789)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals(None,
                      self.getMetricValues(events, interactions))

  def testResultsGroupingByMetric(self):
    metrics = memory_timeline.REPORTED_METRICS
    offset = len(metrics)
    stats1 = {metric: value for value, metric in enumerate(metrics)}
    stats2 = {metric: value for value, metric in enumerate(metrics, offset)}
    expected = {metric: [value, value + offset]
                for value, metric in enumerate(metrics)}
    events = [MockMemoryDump(2, 4, stats1),
              MockMemoryDump(5, 6, stats2)]
    interactions = [TestInteraction(1, 10)]
    self.assertEquals(expected,
                      self.getResultsDict(events, interactions))
