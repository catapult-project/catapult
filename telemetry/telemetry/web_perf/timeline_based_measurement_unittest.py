# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators
from telemetry.core import platform
from telemetry.core import wpr_modes
from telemetry.page import page as page_module
from telemetry.page import page_set
from telemetry.results import page_test_results
from telemetry.timeline import model as model_module
from telemetry.timeline import async_slice
from telemetry.unittest_util import browser_test_case
from telemetry.unittest_util import options_for_unittests
from telemetry.unittest_util import page_test_test_case
from telemetry.value import scalar
from telemetry.web_perf import timeline_based_measurement as tbm_module
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import timeline_based_metric


class FakeSmoothMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeSmoothMetric', 'ms', 1))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'SmoothMetricRecords', 'count',
        len(interaction_records)))


class FakeLoadingMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeLoadingMetric', 'ms', 2))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'LoadingMetricRecords', 'count',
        len(interaction_records)))


class TimelineBasedMetricTestData(object):

  def __init__(self):
    self._model = model_module.TimelineModel()
    renderer_process = self._model.GetOrCreateProcess(1)
    self._renderer_thread = renderer_process.GetOrCreateThread(2)
    self._renderer_thread.name = 'CrRendererMain'
    self._foo_thread = renderer_process.GetOrCreateThread(3)
    self._foo_thread.name = 'CrFoo'

    self._results = page_test_results.PageTestResults()
    self._ps = None
    self._threads_to_records_map = None

  @property
  def model(self):
    return self._model

  @property
  def renderer_thread(self):
    return self._renderer_thread

  @property
  def foo_thread(self):
    return self._foo_thread

  @property
  def threads_to_records_map(self):
    return self._threads_to_records_map

  @property
  def results(self):
    return self._results

  def AddInteraction(self, thread, marker='', ts=0, duration=5):
    assert thread in (self._renderer_thread, self._foo_thread)
    thread.async_slices.append(async_slice.AsyncSlice(
        'category', marker, timestamp=ts, duration=duration,
        start_thread=self._renderer_thread, end_thread=self._renderer_thread,
        thread_start=ts, thread_duration=duration))

  def FinalizeImport(self):
    self._model.FinalizeImport()
    self._threads_to_records_map = (
      tbm_module._GetRendererThreadsToInteractionRecordsMap(self._model))
    self._ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    self._ps.AddUserStory(page_module.Page(
        'http://www.bar.com/', self._ps, self._ps.base_dir))
    self._results.WillRunPage(self._ps.pages[0])

  def AddResults(self):
    for thread, records in self._threads_to_records_map.iteritems():
      metric = tbm_module._TimelineBasedMetrics(  # pylint: disable=W0212
        self._model, thread, records)
      metric.AddResults(self._results)
    self._results.DidRunPage(self._ps.pages[0])


class TimelineBasedMetricsTests(unittest.TestCase):

  def setUp(self):
    self.actual_get_all_tbm_metrics = tbm_module._GetAllTimelineBasedMetrics
    fake_tbm_metrics = (FakeSmoothMetric(), FakeLoadingMetric())
    tbm_module._GetAllTimelineBasedMetrics = lambda: fake_tbm_metrics

  def tearDown(self):
    tbm_module._GetAllTimelineBasedMetrics = self.actual_get_all_tbm_metrics

  def testGetRendererThreadsToInteractionRecordsMap(self):
    d = TimelineBasedMetricTestData()
    # Insert 2 interaction records to renderer_thread and 1 to foo_thread
    d.AddInteraction(d.renderer_thread, ts=0, duration=20,
                     marker='Interaction.LogicalName1/is_smooth')
    d.AddInteraction(d.renderer_thread, ts=25, duration=5,
                     marker='Interaction.LogicalName2/')
    d.AddInteraction(d.foo_thread, ts=50, duration=15,
                     marker='Interaction.LogicalName3/is_smooth')
    d.FinalizeImport()

    self.assertEquals(2, len(d.threads_to_records_map))

    # Assert the 2 interaction records of renderer_thread are in the map.
    self.assertIn(d.renderer_thread, d.threads_to_records_map)
    interactions = d.threads_to_records_map[d.renderer_thread]
    self.assertEquals(2, len(interactions))
    self.assertTrue(interactions[0].is_smooth)
    self.assertEquals(0, interactions[0].start)
    self.assertEquals(20, interactions[0].end)

    self.assertEquals(25, interactions[1].start)
    self.assertEquals(30, interactions[1].end)

    # Assert the 1 interaction records of foo_thread is in the map.
    self.assertIn(d.foo_thread, d.threads_to_records_map)
    interactions = d.threads_to_records_map[d.foo_thread]
    self.assertEquals(1, len(interactions))
    self.assertTrue(interactions[0].is_smooth)
    self.assertEquals(50, interactions[0].start)
    self.assertEquals(65, interactions[0].end)

  def testAddResults(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(d.renderer_thread, ts=0, duration=20,
                     marker='Interaction.LogicalName1/is_smooth')
    d.AddInteraction(d.foo_thread, ts=25, duration=5,
                     marker='Interaction.LogicalName2')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'LogicalName1-FakeSmoothMetric')))
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'LogicalName2-FakeLoadingMetric')))

  def testDuplicateInteractionsInDifferentThreads(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.AddInteraction(d.foo_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth')
    self.assertRaises(tbm_module.InvalidInteractions, d.FinalizeImport)

  def testDuplicateRepeatableInteractionsInDifferentThreads(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.AddInteraction(d.foo_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    self.assertRaises(tbm_module.InvalidInteractions, d.FinalizeImport)


  def testDuplicateUnrepeatableInteractionsInSameThread(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth')
    d.AddInteraction(d.renderer_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth')
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)

  def testDuplicateRepeatableInteractions(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.AddInteraction(d.renderer_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.pages_that_succeeded))

  def testDuplicateRepeatableInteractionsWithDifferentMetrics(self):
    d = TimelineBasedMetricTestData()

    responsive_marker = 'Interaction.LogicalName/repeatable'
    d.AddInteraction(
      d.renderer_thread, ts=10, duration=5, marker=responsive_marker)
    smooth_marker = 'Interaction.LogicalName/is_smooth,repeatable'
    d.AddInteraction(d.renderer_thread, ts=20, duration=5, marker=smooth_marker)
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)


class TestTimelinebasedMeasurementPage(page_module.Page):

  def __init__(self, ps, base_dir, trigger_animation=False,
               trigger_jank=False, trigger_slow=False):
    super(TestTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', ps, base_dir)
    self._trigger_animation = trigger_animation
    self._trigger_jank = trigger_jank
    self._trigger_slow = trigger_slow

  def RunPageInteractions(self, action_runner):
    if self._trigger_animation:
      action_runner.TapElement('#animating-button')
      action_runner.WaitForJavaScriptCondition('window.animationDone')
    if self._trigger_jank:
      action_runner.TapElement('#jank-button')
      action_runner.WaitForJavaScriptCondition('window.jankScriptDone')
    if self._trigger_slow:
      action_runner.TapElement('#slow-button')
      action_runner.WaitForJavaScriptCondition('window.slowScriptDone')


class TimelineBasedMeasurementTest(page_test_test_case.PageTestTestCase):

  def setUp(self):
    browser_test_case.teardown_browser()
    self._options = options_for_unittests.GetCopy()
    self._options.browser_options.wpr_mode = wpr_modes.WPR_OFF

  # This test is flaky when run in parallel on the mac: crbug.com/426676
  # Also, fails on android: crbug.com/437057
  @decorators.Disabled('android', 'mac')
  def testSmoothnessTimelineBasedMeasurementForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddUserStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_animation=True))

    tbm = tbm_module.TimelineBasedMeasurement(tbm_module.Options())
    measurement = tbm_module.TimelineBasedPageTest(tbm)
    results = self.RunMeasurement(measurement, ps,
                                  options=self._options)

    self.assertEquals(0, len(results.failures))
    v = results.FindAllPageSpecificValuesNamed(
        'CenterAnimation-frame_time_discrepancy')
    self.assertEquals(len(v), 1)
    v = results.FindAllPageSpecificValuesNamed(
        'DrawerAnimation-frame_time_discrepancy')
    self.assertEquals(len(v), 1)

  # Disabled since mainthread_jank metric is not supported on windows platform.
  # Also, flaky on the mac when run in parallel: crbug.com/426676
  # Also, fails on android: crbug.com/437057
  @decorators.Disabled('android', 'win', 'mac')
  def testMainthreadJankTimelineBasedMeasurement(self):
    ps = self.CreateEmptyPageSet()
    ps.AddUserStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_jank=True))

    tbm = tbm_module.TimelineBasedMeasurement(tbm_module.Options())
    measurement = tbm_module.TimelineBasedPageTest(tbm)
    results = self.RunMeasurement(measurement, ps,
                                  options=self._options)
    self.assertEquals(0, len(results.failures))

    # In interaction_enabled_page.html, we create a jank loop based on
    # window.performance.now() (basically loop for x milliseconds).
    # Since window.performance.now() uses wall-time instead of thread time,
    # we only assert the biggest jank > 50ms here to account for the fact
    # that the browser may deschedule during the jank loop.
    v = results.FindAllPageSpecificValuesNamed(
        'JankThreadJSRun-responsive-biggest_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)

    v = results.FindAllPageSpecificValuesNamed(
        'JankThreadJSRun-responsive-total_big_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)
