# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import benchmark
from telemetry.core import wpr_modes
from telemetry.page import page as page_module
from telemetry.page import page_measurement_unittest_base
from telemetry.page import page_set
from telemetry.page import page as page_module
from telemetry.results import page_test_results
from telemetry.timeline import async_slice
from telemetry.timeline import model as model_module
from telemetry.unittest import options_for_unittests
from telemetry.value import scalar
from telemetry.web_perf import timeline_based_measurement as tbm_module
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import timeline_based_metric


class FakeFastMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeFastMetric', 'ms', 1))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FastMetricRecords', 'count',
        len(interaction_records)))


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


def GetMetricFromMetricType(metric_type):
  if metric_type == tir_module.IS_FAST:
    return FakeFastMetric()
  if metric_type == tir_module.IS_SMOOTH:
    return FakeSmoothMetric()
  if metric_type == tir_module.IS_RESPONSIVE:
    return FakeLoadingMetric()
  raise Exception('Unrecognized metric type: %s' % metric_type)


class TimelineBasedMetricTestData(object):

  def __init__(self):
    self._model = model_module.TimelineModel()
    renderer_process = self._model.GetOrCreateProcess(1)
    self._renderer_thread = renderer_process.GetOrCreateThread(2)
    self._renderer_thread.name = 'CrRendererMain'
    self._results = page_test_results.PageTestResults()
    self._metric = None
    self._ps = None

  @property
  def results(self):
    return self._results

  @property
  def metric(self):
    return self._metric

  def AddInteraction(self, marker='', ts=0, duration=5):
    self._renderer_thread.async_slices.append(async_slice.AsyncSlice(
        'category', marker, timestamp=ts, duration=duration,
        start_thread=self._renderer_thread, end_thread=self._renderer_thread,
        thread_start=ts, thread_duration=duration))

  def FinalizeImport(self):
    self._model.FinalizeImport()
    self._metric = tbm_module._TimelineBasedMetrics(  # pylint: disable=W0212
        self._model, self._renderer_thread, GetMetricFromMetricType)
    self._ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    self._ps.AddPageWithDefaultRunNavigate('http://www.bar.com/')
    self._results.WillRunPage(self._ps.pages[0])

  def AddResults(self):
    self._metric.AddResults(self._results)
    self._results.DidRunPage(self._ps.pages[0])


class TimelineBasedMetricsTests(unittest.TestCase):

  def testFindTimelineInteractionRecords(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(ts=0, duration=20,
                     marker='Interaction.LogicalName1/is_smooth')
    d.AddInteraction(ts=25, duration=5,
                     marker='Interaction.LogicalName2/is_responsive')
    d.AddInteraction(ts=50, duration=15,
                     marker='Interaction.LogicalName3/is_fast')
    d.FinalizeImport()
    interactions = d.metric.FindTimelineInteractionRecords()
    self.assertEquals(3, len(interactions))
    self.assertTrue(interactions[0].is_smooth)
    self.assertEquals(0, interactions[0].start)
    self.assertEquals(20, interactions[0].end)

    self.assertTrue(interactions[1].is_responsive)
    self.assertEquals(25, interactions[1].start)
    self.assertEquals(30, interactions[1].end)

    self.assertTrue(interactions[2].is_fast)
    self.assertEquals(50, interactions[2].start)
    self.assertEquals(65, interactions[2].end)

  def testAddResults(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(ts=0, duration=20,
                     marker='Interaction.LogicalName1/is_smooth')
    d.AddInteraction(ts=25, duration=5,
                     marker='Interaction.LogicalName2/is_responsive')
    d.AddInteraction(ts=50, duration=15,
                     marker='Interaction.LogicalName3/is_fast')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'LogicalName1-FakeSmoothMetric')))
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'LogicalName2-FakeLoadingMetric')))
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'LogicalName3-FakeFastMetric')))

  def testNoInteractions(self):
    d = TimelineBasedMetricTestData()
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)

  def testDuplicateUnrepeatableInteractions(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth')
    d.AddInteraction(ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth')
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)

  def testDuplicateRepeatableInteractions(self):
    d = TimelineBasedMetricTestData()
    d.AddInteraction(ts=10, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.AddInteraction(ts=20, duration=5,
                     marker='Interaction.LogicalName/is_smooth,repeatable')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.pages_that_succeeded))

  def testDuplicateRepeatableInteractionsWithDifferentMetrics(self):
    d = TimelineBasedMetricTestData()

    responsive_marker = 'Interaction.LogicalName/is_responsive,repeatable'
    d.AddInteraction(ts=10, duration=5, marker=responsive_marker)
    smooth_marker = 'Interaction.LogicalName/is_smooth,repeatable'
    d.AddInteraction(ts=20, duration=5, marker=smooth_marker)
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)


class TestTimelinebasedMeasurementPage(page_module.Page):

  def __init__(self, ps, base_dir, trigger_animation=False,
               trigger_jank=False):
    super(TestTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', ps, base_dir)
    self._trigger_animation = trigger_animation
    self._trigger_jank = trigger_jank

  def RunSmoothness(self, action_runner):
    if self._trigger_animation:
      action_runner.TapElement('#animating-button')
      action_runner.WaitForJavaScriptCondition('window.animationDone')
    if self._trigger_jank:
      action_runner.TapElement('#jank-button')
      action_runner.WaitForJavaScriptCondition('window.jankScriptDone')


class TimelineBasedMeasurementTest(
    page_measurement_unittest_base.PageMeasurementUnitTestBase):

  def setUp(self):
    self._options = options_for_unittests.GetCopy()
    self._options.browser_options.wpr_mode = wpr_modes.WPR_OFF

  def testSmoothnessTimelineBasedMeasurementForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddPage(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_animation=True))

    measurement = tbm_module.TimelineBasedMeasurement()
    results = self.RunMeasurement(measurement, ps,
                                  options=self._options)

    self.assertEquals(0, len(results.failures))
    v = results.FindAllPageSpecificValuesNamed('CenterAnimation-jank')
    self.assertEquals(len(v), 1)
    v = results.FindAllPageSpecificValuesNamed('DrawerAnimation-jank')
    self.assertEquals(len(v), 1)

  # Disabled since mainthread_jank metric is not supported on windows platform.
  @benchmark.Disabled('win')
  def testMainthreadJankTimelineBasedMeasurement(self):
    ps = self.CreateEmptyPageSet()
    ps.AddPage(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, trigger_jank=True))

    measurement = tbm_module.TimelineBasedMeasurement()
    results = self.RunMeasurement(measurement, ps,
                                  options=self._options)
    self.assertEquals(0, len(results.failures))

    # In interaction_enabled_page.html, we create a jank loop based on
    # window.performance.now() (basically loop for x milliseconds).
    # Since window.performance.now() uses wall-time
    # instead of thread time, we set time to looping to 100ms in
    # interaction_enabled_page.html and only assert the biggest jank > 50ms here
    # to  account for the fact that the browser may deschedule during the jank
    # loop.
    v = results.FindAllPageSpecificValuesNamed(
        'JankThreadJSRun-responsive-biggest_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)

    v = results.FindAllPageSpecificValuesNamed(
        'JankThreadJSRun-responsive-total_big_jank_thread_time')
    self.assertGreaterEqual(v[0].value, 50)
