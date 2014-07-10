# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import benchmark
from telemetry.core import wpr_modes
from telemetry.timeline import model as model_module
from telemetry.timeline import async_slice
from telemetry.page import page_measurement_unittest_base
from telemetry.page import page_set
from telemetry.page import page as page_module
from telemetry.results import page_measurement_results
from telemetry.unittest import options_for_unittests
from telemetry.web_perf import timeline_based_measurement as tbm_module
from telemetry.web_perf.metrics import timeline_based_metric


class TimelineBasedMetricsTests(unittest.TestCase):

  def setUp(self):
    model = model_module.TimelineModel()
    renderer_thread = model.GetOrCreateProcess(1).GetOrCreateThread(2)
    renderer_thread.name = 'CrRendererMain'

    # [      X       ]
    #      [  Y  ]
    renderer_thread.BeginSlice('cat1', 'x.y', 10, 0)
    renderer_thread.EndSlice(20, 20)

    renderer_thread.async_slices.append(async_slice.AsyncSlice(
        'cat', 'Interaction.LogicalName1/is_smooth',
        timestamp=0, duration=20,
        start_thread=renderer_thread, end_thread=renderer_thread,
        thread_start=5, thread_duration=15))
    renderer_thread.async_slices.append(async_slice.AsyncSlice(
        'cat', 'Interaction.LogicalName2/is_responsive',
        timestamp=25, duration=5,
        start_thread=renderer_thread, end_thread=renderer_thread,
        thread_start=25, thread_duration=5))
    model.FinalizeImport()

    self.model = model
    self.renderer_thread = renderer_thread

  def testFindTimelineInteractionRecords(self):
    metric = tbm_module._TimelineBasedMetrics(  # pylint: disable=W0212
      self.model, self.renderer_thread, lambda _: [])
    interactions = metric.FindTimelineInteractionRecords()
    self.assertEquals(2, len(interactions))
    self.assertTrue(interactions[0].is_smooth)
    self.assertEquals(0, interactions[0].start)
    self.assertEquals(20, interactions[0].end)

    self.assertTrue(interactions[1].is_responsive)
    self.assertEquals(25, interactions[1].start)
    self.assertEquals(30, interactions[1].end)

  def testAddResults(self):
    results = page_measurement_results.PageMeasurementResults()

    class FakeSmoothMetric(timeline_based_metric.TimelineBasedMetric):

      def AddResults(self, model, renderer_thread,
                     interaction_records, results):
        results.Add('FakeSmoothMetric', 'ms', 1)

    class FakeLoadingMetric(timeline_based_metric.TimelineBasedMetric):

      def AddResults(self, model, renderer_thread,
                     interaction_records, results):
        for r in interaction_records:
          assert r.logical_name == 'LogicalName2'
        results.Add('FakeLoadingMetric', 'ms', 2)

    def CreateMetricsForTimelineInteractionRecord(interaction):
      res = []
      if interaction.is_smooth:
        res.append(FakeSmoothMetric())
      if interaction.is_responsive:
        res.append(FakeLoadingMetric())
      return res

    metric = tbm_module._TimelineBasedMetrics(  # pylint: disable=W0212
        self.model, self.renderer_thread,
        CreateMetricsForTimelineInteractionRecord)
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddPageWithDefaultRunNavigate('http://www.bar.com/')

    results.WillMeasurePage(ps.pages[0])
    metric.AddResults(results)
    results.DidMeasurePage()

    v = results.FindAllPageSpecificValuesNamed('LogicalName1-FakeSmoothMetric')
    self.assertEquals(len(v), 1)
    v = results.FindAllPageSpecificValuesNamed('LogicalName2-FakeLoadingMetric')
    self.assertEquals(len(v), 1)


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
