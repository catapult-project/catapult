# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators
from telemetry import story
from telemetry.internal.results import page_test_results
from telemetry.page import page as page_module
from telemetry.testing import options_for_unittests
from telemetry.testing import page_test_test_case
from telemetry.timeline import async_slice
from telemetry.timeline import chrome_trace_category_filter
from telemetry.timeline import model as model_module
from telemetry.util import wpr_modes
from telemetry.value import improvement_direction
from telemetry.value import scalar
from telemetry.web_perf.metrics import timeline_based_metric
from telemetry.web_perf import timeline_based_measurement as tbm_module
from tracing.value import histogram_set
from tracing.value.diagnostics import date_range
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


class FakeSmoothMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeSmoothMetric', 'ms', 1,
        improvement_direction=improvement_direction.DOWN))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'SmoothMetricRecords', 'count',
        len(interaction_records),
        improvement_direction=improvement_direction.DOWN))


class FakeLoadingMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeLoadingMetric', 'ms', 2,
        improvement_direction=improvement_direction.DOWN))
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'LoadingMetricRecords', 'count',
        len(interaction_records),
        improvement_direction=improvement_direction.DOWN))


class FakeStartupMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interaction_records, results):
    pass

  def AddWholeTraceResults(self, model, results):
    results.AddValue(scalar.ScalarValue(
        results.current_page, 'FakeStartupMetric', 'ms', 3,
        improvement_direction=improvement_direction.DOWN))


class TimelineBasedMetricTestData(object):

  def __init__(self, options):
    self._model = model_module.TimelineModel()
    renderer_process = self._model.GetOrCreateProcess(1)
    self._renderer_thread = renderer_process.GetOrCreateThread(2)
    self._renderer_thread.name = 'CrRendererMain'
    self._foo_thread = renderer_process.GetOrCreateThread(3)
    self._foo_thread.name = 'CrFoo'

    self._results_wrapper = tbm_module._TBMResultWrapper()
    self._results = page_test_results.PageTestResults()
    self._results.telemetry_info.benchmark_name = 'benchmark'
    self._results.telemetry_info.benchmark_start_epoch = 123
    self._results.telemetry_info.benchmark_descriptions = 'foo'
    self._story_set = None
    self._threads_to_records_map = None
    self._tbm_options = options

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
    self._story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    self._story_set.AddStory(page_module.Page(
        'http://www.bar.com/', self._story_set, self._story_set.base_dir,
        name='http://www.bar.com/'))
    self._results.WillRunPage(self._story_set.stories[0])

  def AddResults(self):
    all_metrics = self._tbm_options.GetLegacyTimelineBasedMetrics()

    for thread, records in self._threads_to_records_map.iteritems():
      # pylint: disable=protected-access
      metric = tbm_module._TimelineBasedMetrics(
          self._model, thread, records, self._results_wrapper, all_metrics)
      metric.AddResults(self._results)

    for metric in all_metrics:
      metric.AddWholeTraceResults(self._model, self._results)

    self._results.DidRunPage(self._story_set.stories[0])


class LegacyTimelineBasedMetricsTests(unittest.TestCase):
  """Tests for LegacyTimelineBasedMetrics (TBMv1), i.e. python model based."""

  def setUp(self):
    self._options = tbm_module.Options()
    self._options.SetLegacyTimelineBasedMetrics(
        (FakeSmoothMetric(), FakeLoadingMetric(), FakeStartupMetric()))

  def testGetRendererThreadsToInteractionRecordsMap(self):
    d = TimelineBasedMetricTestData(self._options)
    # Insert 2 interaction records to renderer_thread and 1 to foo_thread
    d.AddInteraction(d.renderer_thread, ts=0, duration=20,
                     marker='Interaction.LogicalName1')
    d.AddInteraction(d.renderer_thread, ts=25, duration=5,
                     marker='Interaction.LogicalName2')
    d.AddInteraction(d.foo_thread, ts=50, duration=15,
                     marker='Interaction.LogicalName3')
    d.FinalizeImport()

    self.assertEquals(2, len(d.threads_to_records_map))

    # Assert the 2 interaction records of renderer_thread are in the map.
    self.assertIn(d.renderer_thread, d.threads_to_records_map)
    interactions = d.threads_to_records_map[d.renderer_thread]
    self.assertEquals(2, len(interactions))
    self.assertEquals(0, interactions[0].start)
    self.assertEquals(20, interactions[0].end)

    self.assertEquals(25, interactions[1].start)
    self.assertEquals(30, interactions[1].end)

    # Assert the 1 interaction records of foo_thread is in the map.
    self.assertIn(d.foo_thread, d.threads_to_records_map)
    interactions = d.threads_to_records_map[d.foo_thread]
    self.assertEquals(1, len(interactions))
    self.assertEquals(50, interactions[0].start)
    self.assertEquals(65, interactions[0].end)

  def testAddResults(self):
    d = TimelineBasedMetricTestData(self._options)
    d.AddInteraction(d.renderer_thread, ts=0, duration=20,
                     marker='Interaction.LogicalName1')
    d.AddInteraction(d.foo_thread, ts=25, duration=5,
                     marker='Interaction.LogicalName2')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesFromIRNamed(
        'LogicalName1', 'FakeSmoothMetric')))
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesFromIRNamed(
        'LogicalName2', 'FakeLoadingMetric')))
    self.assertEquals(1, len(d.results.FindAllPageSpecificValuesNamed(
        'FakeStartupMetric')))

  def testDuplicateInteractionsInDifferentThreads(self):
    d = TimelineBasedMetricTestData(self._options)
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/repeatable')
    d.AddInteraction(d.foo_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName')
    self.assertRaises(tbm_module.InvalidInteractions, d.FinalizeImport)

  def testDuplicateRepeatableInteractionsInDifferentThreads(self):
    d = TimelineBasedMetricTestData(self._options)
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/repeatable')
    d.AddInteraction(d.foo_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/repeatable')
    self.assertRaises(tbm_module.InvalidInteractions, d.FinalizeImport)

  def testDuplicateUnrepeatableInteractionsInSameThread(self):
    d = TimelineBasedMetricTestData(self._options)
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName')
    d.AddInteraction(d.renderer_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName')
    d.FinalizeImport()
    self.assertRaises(tbm_module.InvalidInteractions, d.AddResults)

  def testDuplicateRepeatableInteractions(self):
    d = TimelineBasedMetricTestData(self._options)
    d.AddInteraction(d.renderer_thread, ts=10, duration=5,
                     marker='Interaction.LogicalName/repeatable')
    d.AddInteraction(d.renderer_thread, ts=20, duration=5,
                     marker='Interaction.LogicalName/repeatable')
    d.FinalizeImport()
    d.AddResults()
    self.assertEquals(1, len(d.results.pages_that_succeeded))


class TestTimelinebasedMeasurementPage(page_module.Page):
  """A page used to test TBMv2 measurements."""

  def __init__(self, ps, base_dir, trigger_animation=False,
               trigger_jank=False, trigger_slow=False,
               trigger_scroll_gesture=False, measure_memory=False):
    super(TestTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', ps, base_dir,
        name='interaction_enabled_page.html')
    self._trigger_animation = trigger_animation
    self._trigger_jank = trigger_jank
    self._trigger_slow = trigger_slow
    self._trigger_scroll_gesture = trigger_scroll_gesture
    self._measure_memory = measure_memory

  def RunPageInteractions(self, action_runner):
    if self._measure_memory:
      action_runner.MeasureMemory()
    if self._trigger_animation:
      action_runner.TapElement('#animating-button')
      action_runner.WaitForJavaScriptCondition('window.animationDone')
    if self._trigger_jank:
      action_runner.TapElement('#jank-button')
      action_runner.WaitForJavaScriptCondition('window.jankScriptDone')
    if self._trigger_slow:
      action_runner.TapElement('#slow-button')
      action_runner.WaitForJavaScriptCondition('window.slowScriptDone')
    if self._trigger_scroll_gesture:
      with action_runner.CreateGestureInteraction('Scroll'):
        action_runner.ScrollPage()

class FailedTimelinebasedMeasurementPage(page_module.Page):

  def __init__(self, ps, base_dir):
    super(FailedTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', ps, base_dir,
        name='interaction_enabled_page.html')

  def RunPageInteractions(self, action_runner):
    action_runner.TapElement('#does-not-exist')


class TimelineBasedMeasurementTest(page_test_test_case.PageTestTestCase):
  """Tests for TimelineBasedMetrics (TBMv2), i.e. //tracing/tracing/metrics."""

  def setUp(self):
    self._options = self.createDefaultRunnerOptions()

  def createDefaultRunnerOptions(self):
    runner_options = options_for_unittests.GetCopy()
    runner_options.browser_options.wpr_mode = wpr_modes.WPR_OFF
    return runner_options

  @decorators.Disabled('chromeos')
  @decorators.Isolated
  def testTraceCaptureUponFailure(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(FailedTimelinebasedMeasurementPage(ps, ps.base_dir))

    options = tbm_module.Options()
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['sampleMetric'])

    tbm = tbm_module.TimelineBasedMeasurement(options)
    results = self.RunMeasurement(tbm, ps, self._options)

    self.assertTrue(results.had_failures)
    self.assertEquals(1, len(results.FindAllTraceValues()))

  # Fails on chromeos: crbug.com/483212
  @decorators.Disabled('chromeos')
  @decorators.Isolated
  def testTBM2ForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(ps, ps.base_dir))

    options = tbm_module.Options()
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['sampleMetric'])

    tbm = tbm_module.TimelineBasedMeasurement(options)
    results = self.RunMeasurement(tbm, ps, self._options)

    self.assertFalse(results.had_failures)

    histogram_dicts = results.AsHistogramDicts()
    hs = histogram_set.HistogramSet()
    hs.ImportDicts(histogram_dicts)
    self.assertEquals(4, len(hs))
    hist = hs.GetFirstHistogram()
    benchmarks = hist.diagnostics.get(reserved_infos.BENCHMARKS.name)
    self.assertIsInstance(benchmarks, generic_set.GenericSet)
    self.assertEquals(1, len(benchmarks))
    self.assertEquals('', list(benchmarks)[0])
    stories = hist.diagnostics.get(reserved_infos.STORIES.name)
    self.assertIsInstance(stories, generic_set.GenericSet)
    self.assertEquals(1, len(stories))
    self.assertEquals('interaction_enabled_page.html', list(stories)[0])
    repeats = hist.diagnostics.get(reserved_infos.STORYSET_REPEATS.name)
    self.assertIsInstance(repeats, generic_set.GenericSet)
    self.assertEquals(1, len(repeats))
    self.assertEquals(0, list(repeats)[0])
    hist = hs.GetFirstHistogram()
    trace_start = hist.diagnostics.get(reserved_infos.TRACE_START.name)
    self.assertIsInstance(trace_start, date_range.DateRange)

    v_foo = results.FindAllPageSpecificValuesNamed('foo_avg')
    self.assertEquals(len(v_foo), 1)
    self.assertEquals(v_foo[0].value, 50)
    self.assertIsNotNone(v_foo[0].page)

  # Disabled flags: crbug.com/765114.
  @decorators.Disabled('reference')
  @decorators.Disabled('win', 'chromeos')
  @decorators.Isolated
  def testHeapProfilerForSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(
        ps, ps.base_dir, measure_memory=True, trigger_slow=True))

    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='-*,disabled-by-default-memory-infra')
    options = tbm_module.Options(overhead_level=cat_filter)
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['memoryMetric'])

    runner_options = self.createDefaultRunnerOptions()
    runner_options.browser_options.AppendExtraBrowserArgs(
        ['--memlog=all', '--memlog-sampling', '--memlog-stack-mode=pseudo'])
    tbm = tbm_module.TimelineBasedMeasurement(options)
    results = self.RunMeasurement(tbm, ps, runner_options)

    self.assertFalse(results.had_failures)

    DUMP_COUNT_METRIC = 'memory:chrome:all_processes:dump_count'
    dumps_detailed = results.FindAllPageSpecificValuesNamed(
        DUMP_COUNT_METRIC + ':detailed_avg')
    dumps_heap_profiler = results.FindAllPageSpecificValuesNamed(
        DUMP_COUNT_METRIC + ':heap_profiler_avg')
    self.assertEquals(1, len(dumps_detailed))
    self.assertEquals(1, len(dumps_heap_profiler))
    self.assertGreater(dumps_detailed[0].value, 0)
    self.assertEquals(dumps_detailed[0].value, dumps_heap_profiler[0].value)

  # TODO(ksakamoto): enable this in reference once the reference build of
  # telemetry is updated.
  @decorators.Disabled('reference')
  @decorators.Disabled('chromeos')
  def testFirstPaintMetricSmoke(self):
    ps = self.CreateEmptyPageSet()
    ps.AddStory(TestTimelinebasedMeasurementPage(ps, ps.base_dir))

    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='*,blink.console,navigation,blink.user_timing,loading,' +
        'devtools.timeline,disabled-by-default-blink.debug.layout')

    options = tbm_module.Options(overhead_level=cat_filter)
    options.SetTimelineBasedMetrics(['loadingMetric'])

    tbm = tbm_module.TimelineBasedMeasurement(options)
    results = self.RunMeasurement(tbm, ps, self._options)

    self.assertFalse(results.had_failures)
    v_ttfcp_max = results.FindAllPageSpecificValuesNamed(
        'timeToFirstContentfulPaint_max')
    self.assertEquals(len(v_ttfcp_max), 1)
    self.assertIsNotNone(v_ttfcp_max[0].page)
    self.assertGreater(v_ttfcp_max[0].value, 0)

    v_ttfmp_max = results.FindAllPageSpecificValuesNamed(
        'timeToFirstMeaningfulPaint_max')
    self.assertEquals(len(v_ttfmp_max), 1)
    self.assertIsNotNone(v_ttfmp_max[0].page)
