# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shutil
import tempfile

from telemetry import decorators
from telemetry.page import page as page_module
from telemetry.testing import options_for_unittests
from telemetry.testing import page_test_test_case
from telemetry.timeline import chrome_trace_category_filter
from telemetry.web_perf import timeline_based_measurement as tbm_module
from tracing.value import histogram_set
from tracing.value.diagnostics import date_range
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


class TestTimelinebasedMeasurementPage(page_module.Page):
  """A page used to test TBMv2 measurements."""

  def __init__(self, story_set, base_dir, trigger_animation=False,
               trigger_jank=False, trigger_slow=False,
               trigger_scroll_gesture=False, measure_memory=False):
    super(TestTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', story_set, base_dir,
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

  def __init__(self, story_set, base_dir):
    super(FailedTimelinebasedMeasurementPage, self).__init__(
        'file://interaction_enabled_page.html', story_set, base_dir,
        name='interaction_enabled_page.html')

  def RunPageInteractions(self, action_runner):
    action_runner.TapElement('#does-not-exist')


class TimelineBasedMeasurementTest(page_test_test_case.PageTestTestCase):
  """Tests for TimelineBasedMetrics (TBMv2), i.e. //tracing/tracing/metrics."""

  def setUp(self):
    self._options = options_for_unittests.GetRunOptions(
        output_dir=tempfile.mkdtemp())

  def tearDown(self):
    shutil.rmtree(self._options.output_dir)

  @decorators.Disabled('chromeos')
  @decorators.Disabled('win')  # crbug.com/956812
  @decorators.Isolated
  def testTraceCaptureUponFailure(self):
    story_set = self.CreateEmptyPageSet()
    story_set.AddStory(
        FailedTimelinebasedMeasurementPage(story_set, story_set.base_dir))

    options = tbm_module.Options()
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['sampleMetric'])
    tbm = tbm_module.TimelineBasedMeasurement(options)

    results = self.RunMeasurement(tbm, story_set, run_options=self._options)

    self.assertTrue(results.had_failures)
    runs = list(results.IterRunsWithTraces())
    self.assertEquals(1, len(runs))

  # Fails on chromeos: crbug.com/483212
  @decorators.Disabled('chromeos')
  @decorators.Isolated
  def testTBM2ForSmoke(self):
    story_set = self.CreateEmptyPageSet()
    story_set.AddStory(
        TestTimelinebasedMeasurementPage(story_set, story_set.base_dir))

    options = tbm_module.Options()
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['sampleMetric'])
    tbm = tbm_module.TimelineBasedMeasurement(options)

    results = self.RunMeasurement(tbm, story_set, run_options=self._options)

    self.assertFalse(results.had_failures)

    histogram_dicts = results.AsHistogramDicts()
    hs = histogram_set.HistogramSet()
    hs.ImportDicts(histogram_dicts)
    self.assertEquals(4, len(hs))
    hist = hs.GetFirstHistogram()
    benchmarks = hist.diagnostics.get(reserved_infos.BENCHMARKS.name)
    self.assertIsInstance(benchmarks, generic_set.GenericSet)
    self.assertEquals(1, len(benchmarks))
    self.assertEquals(page_test_test_case.BENCHMARK_NAME,
                      list(benchmarks)[0])
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

  @decorators.Disabled('reference')
  @decorators.Disabled('win', 'chromeos')  # https://crbug.com/765114
  @decorators.Disabled('mac', 'linux')  # https://crbug.com/956812
  @decorators.Isolated
  def testHeapProfilerForSmoke(self):
    story_set = self.CreateEmptyPageSet()
    story_set.AddStory(TestTimelinebasedMeasurementPage(
        story_set, story_set.base_dir, measure_memory=True, trigger_slow=True))

    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='-*,disabled-by-default-memory-infra')
    options = tbm_module.Options(overhead_level=cat_filter)
    options.config.enable_chrome_trace = True
    options.SetTimelineBasedMetrics(['memoryMetric'])
    tbm = tbm_module.TimelineBasedMeasurement(options)

    self._options.browser_options.AppendExtraBrowserArgs(
        ['--memlog=all', '--memlog-sampling', '--memlog-stack-mode=pseudo'])
    results = self.RunMeasurement(tbm, story_set, run_options=self._options)

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
  # Disabled on all platforms due to flakiness: https://crbug.com/947269.
  @decorators.Disabled('reference')
  @decorators.Disabled('all')
  def testFirstPaintMetricSmoke(self):
    story_set = self.CreateEmptyPageSet()
    story_set.AddStory(
        TestTimelinebasedMeasurementPage(story_set, story_set.base_dir))

    cat_filter = chrome_trace_category_filter.ChromeTraceCategoryFilter(
        filter_string='*,blink.console,navigation,blink.user_timing,loading,' +
        'devtools.timeline,disabled-by-default-blink.debug.layout')

    options = tbm_module.Options(overhead_level=cat_filter)
    options.SetTimelineBasedMetrics(['loadingMetric'])

    tbm = tbm_module.TimelineBasedMeasurement(options)
    results = self.RunMeasurement(tbm, story_set, run_options=self._options)

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
