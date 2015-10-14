# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import unittest

from telemetry.internal.results import page_test_results
from telemetry.page import page
import mock
from telemetry.timeline import memory_dump_event
from telemetry.web_perf.metrics import memory_timeline
from telemetry.web_perf import timeline_interaction_record


def MockProcessDumpEvent(dump_id, name, start, memory_usage):
  process_dump = mock.Mock()
  process_dump.dump_id = dump_id
  process_dump.process_name = name
  process_dump.start = start
  if memory_usage is None:
    memory_usage = {}
  elif not isinstance(memory_usage, dict):
    memory_usage = dict.fromkeys(memory_timeline.DEFAULT_METRICS, memory_usage)
  process_dump.has_mmaps = any(metric in memory_usage for metric
                               in memory_timeline.DEFAULT_METRICS)
  process_dump.GetMemoryUsage = mock.Mock(return_value=memory_usage)
  return process_dump


def MockTimelineModel(process_dumps):
  dumps_by_id = collections.defaultdict(list)
  for process_dump in process_dumps:
    dumps_by_id[process_dump.dump_id].append(process_dump)

  global_dumps = sorted((memory_dump_event.GlobalMemoryDump(dumps)
                         for dumps in dumps_by_id.itervalues()),
                        key=lambda dump: dump.start)

  mock_model = mock.Mock()
  mock_model.IterGlobalMemoryDumps = mock.Mock(return_value=global_dumps)
  return mock_model


def TestInteraction(start, end):
  return timeline_interaction_record.TimelineInteractionRecord(
      'Action_TestInteraction', start, end)


class MemoryTimelineMetricUnitTest(unittest.TestCase):
  def getResultsDict(self, model, interactions):
    def strip_prefix(key, prefix):
      self.assertTrue(key.startswith(prefix))
      return key[len(prefix):]

    results = page_test_results.PageTestResults()
    test_page = page.Page('http://google.com')
    results.WillRunPage(test_page)
    metric = memory_timeline.MemoryTimelineMetric()
    metric.AddResults(model, None, interactions, results)
    result_dict = {strip_prefix(v.name, 'memory_'): v.values
                   for v in results.current_page_run.values}
    results.DidRunPage(test_page)
    return result_dict

  def getOverallPssTotal(self, model, interactions):
    results = self.getResultsDict(model, interactions)
    self.assertTrue('mmaps_overall_pss_total' in results)
    return results['mmaps_overall_pss_total']

  def testSingleMemoryDump(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, 123)])
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123], self.getOverallPssTotal(model, interactions))

  def testMultipleMemoryDumps(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, 123),
        MockProcessDumpEvent('dump2', 'browser', 5, 456)])
    interactions = [TestInteraction(1, 10)]
    self.assertEquals([123, 456], self.getOverallPssTotal(model, interactions))

  def testMultipleInteractions(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, 123),
        MockProcessDumpEvent('dump2', 'browser', 5, 456),
        MockProcessDumpEvent('dump3', 'browser', 13, 789)])
    interactions = [TestInteraction(1, 10),
                    TestInteraction(12, 15)]
    self.assertEquals([123, 456, 789],
                      self.getOverallPssTotal(model, interactions))

  def testDumpsOutsideInteractionsAreFilteredOut(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 1, 111),
        MockProcessDumpEvent('dump2', 'browser', 5, 123),
        MockProcessDumpEvent('dump3', 'browser', 11, 456),
        MockProcessDumpEvent('dump4', 'browser', 13, 555),
        MockProcessDumpEvent('dump5', 'browser', 17, 789)])
    interactions = [TestInteraction(3, 10),
                    TestInteraction(12, 15)]
    self.assertEquals([123, 555], self.getOverallPssTotal(model, interactions))

  def testDumpsWithNoMemoryMaps(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, {'blink': 123}),
        MockProcessDumpEvent('dump2', 'browser', 5, {'blink': 456})])
    interactions = [TestInteraction(1, 10)]
    results = self.getResultsDict(model, interactions)
    self.assertItemsEqual(['blink_total', 'blink_browser'], results.keys())
    self.assertListEqual([123, 456], results['blink_total'])
    self.assertListEqual([123, 456], results['blink_browser'])

  def testDumpsWithSomeMemoryMaps(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, 123),
        MockProcessDumpEvent('dump2', 'browser', 5, None)])
    interactions = [TestInteraction(1, 10)]
    self.assertRaises(AssertionError, self.getResultsDict, model, interactions)

  def testReturnsNoneWhenAllDumpsAreFilteredOut(self):
    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'bowser', 0, 123),
        MockProcessDumpEvent('dump2', 'browser', 11, 789)])
    interactions = [TestInteraction(1, 10)]
    self.assertEquals(None, self.getOverallPssTotal(model, interactions))

  def testResultsBrokenDownByProcess(self):
    metrics = memory_timeline.DEFAULT_METRICS
    stats1 = {metric: value for value, metric in enumerate(metrics)}
    stats2 = {metric: value for value, metric in enumerate(reversed(metrics))}
    total = len(metrics) - 1

    expected = {}
    expected.update(('%s_browser' % metric, [value])
                    for metric, value in stats1.iteritems())
    expected.update(('%s_gpu_process' % metric, [value])
                    for metric, value in stats2.iteritems())
    expected.update(('%s_total' % metric, [total]) for metric in metrics)

    model = MockTimelineModel([
        MockProcessDumpEvent('dump1', 'browser', 2, stats1),
        MockProcessDumpEvent('dump1', 'GPU Process', 5, stats2)])
    interactions = [TestInteraction(1, 10)]
    self.assertEquals(expected, self.getResultsDict(model, interactions))
