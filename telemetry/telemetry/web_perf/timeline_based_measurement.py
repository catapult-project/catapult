# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.timeline import chrome_trace_category_filter
from telemetry.timeline import tracing_config
from telemetry.web_perf import story_test

# TimelineBasedMeasurement considers all instrumentation as producing a single
# timeline. But, depending on the amount of instrumentation that is enabled,
# overhead increases. The user of the measurement must therefore chose between
# a few levels of instrumentation.
LOW_OVERHEAD_LEVEL = 'low-overhead'
DEFAULT_OVERHEAD_LEVEL = 'default-overhead'
DEBUG_OVERHEAD_LEVEL = 'debug-overhead'

ALL_OVERHEAD_LEVELS = [
    LOW_OVERHEAD_LEVEL,
    DEFAULT_OVERHEAD_LEVEL,
    DEBUG_OVERHEAD_LEVEL,
]


class Options(object):
  """A class to be used to configure TimelineBasedMeasurement.

  This is created and returned by
  Benchmark.CreateCoreTimelineBasedMeasurementOptions.

  """

  def __init__(self, overhead_level=LOW_OVERHEAD_LEVEL):
    """As the amount of instrumentation increases, so does the overhead.
    The user of the measurement chooses the overhead level that is appropriate,
    and the tracing is filtered accordingly.

    overhead_level: Can either be a custom ChromeTraceCategoryFilter object or
        one of LOW_OVERHEAD_LEVEL, DEFAULT_OVERHEAD_LEVEL or
        DEBUG_OVERHEAD_LEVEL.
    """
    self._config = tracing_config.TracingConfig()
    self._config.enable_chrome_trace = True
    self._config.enable_platform_display_trace = False

    if isinstance(overhead_level,
                  chrome_trace_category_filter.ChromeTraceCategoryFilter):
      self._config.chrome_trace_config.SetCategoryFilter(overhead_level)
    elif overhead_level in ALL_OVERHEAD_LEVELS:
      if overhead_level == LOW_OVERHEAD_LEVEL:
        self._config.chrome_trace_config.SetLowOverheadFilter()
      elif overhead_level == DEFAULT_OVERHEAD_LEVEL:
        self._config.chrome_trace_config.SetDefaultOverheadFilter()
      else:
        self._config.chrome_trace_config.SetDebugOverheadFilter()
    else:
      raise Exception("Overhead level must be a ChromeTraceCategoryFilter "
                      "object or valid overhead level string. Given overhead "
                      "level: %s" % overhead_level)

    self._timeline_based_metrics = None


  def ExtendTraceCategoryFilter(self, filters):
    for category_filter in filters:
      self.AddTraceCategoryFilter(category_filter)

  def AddTraceCategoryFilter(self, category_filter):
    self._config.chrome_trace_config.category_filter.AddFilter(category_filter)

  @property
  def category_filter(self):
    return self._config.chrome_trace_config.category_filter

  @property
  def config(self):
    return self._config

  def ExtendTimelineBasedMetric(self, metrics):
    for metric in metrics:
      self.AddTimelineBasedMetric(metric)

  def AddTimelineBasedMetric(self, metric):
    assert isinstance(metric, basestring)
    if self._timeline_based_metrics is None:
      self._timeline_based_metrics = []
    self._timeline_based_metrics.append(metric)

  def SetTimelineBasedMetrics(self, metrics):
    """Sets the new-style (TBMv2) metrics to run.

    Metrics are assumed to live in //tracing/tracing/metrics, so the path you
    pass in should be relative to that. For example, to specify
    sample_metric.html, you should pass in ['sample_metric.html'].

    Args:
      metrics: A list of strings giving metric paths under
          //tracing/tracing/metrics.
    """
    assert isinstance(metrics, list)
    for metric in metrics:
      assert isinstance(metric, basestring)
    self._timeline_based_metrics = metrics

  def GetTimelineBasedMetrics(self):
    return self._timeline_based_metrics or []


class TimelineBasedMeasurement(story_test.StoryTest):
  """Collects multiple metrics based on their interaction records.

  A timeline based measurement shifts the burden of what metrics to collect onto
  the story under test. Instead of the measurement
  having a fixed set of values it collects, the story being tested
  issues (via javascript) an Interaction record into the user timing API that
  describing what is happening at that time, as well as a standardized set
  of flags describing the semantics of the work being done. The
  TimelineBasedMeasurement object collects a trace that includes both these
  interaction records, and a user-chosen amount of performance data using
  Telemetry's various timeline-producing APIs, tracing especially.

  It then passes the recorded timeline to different TimelineBasedMetrics based
  on those flags. As an example, this allows a single story run to produce
  load timing data, smoothness data, critical jank information and overall cpu
  usage information.

  Args:
      options: an instance of timeline_based_measurement.Options.
  """
  def __init__(self, options):
    self._tbm_options = options

  def WillRunStory(self, platform):
    """Configure and start tracing."""
    if self._tbm_options.config.enable_chrome_trace:
      # Always enable 'blink.console' and 'v8.console' categories for:
      # 1) Backward compat of chrome clock sync (https://crbug.com/646925).
      # 2) Allows users to add trace event through javascript.
      # 3) For the console error metric (https://crbug.com/880432).
      # Note that these categories are extremely low-overhead, so this doesn't
      # affect the tracing overhead budget much.
      chrome_config = self._tbm_options.config.chrome_trace_config
      chrome_config.category_filter.AddIncludedCategory('blink.console')
      chrome_config.category_filter.AddIncludedCategory('v8.console')
    platform.tracing_controller.StartTracing(self._tbm_options.config)

  def Measure(self, platform, results):
    """Collect all possible metrics and added them to results."""
    platform.tracing_controller.RecordBenchmarkMetadata(results)
    traces = platform.tracing_controller.StopTracing()
    tbm_metrics = self._tbm_options.GetTimelineBasedMetrics()
    tbm_metrics = (
        self._tbm_options.GetTimelineBasedMetrics() +
        results.current_story.GetExtraTracingMetrics())
    assert tbm_metrics, (
        'Please specify required metrics using SetTimelineBasedMetrics')
    results.AddTraces(traces, tbm_metrics=tbm_metrics)

  def DidRunStory(self, platform, results):
    """Clean up after running the story."""
    if platform.tracing_controller.is_tracing_running:
      traces = platform.tracing_controller.StopTracing()
      results.AddTraces(traces)

  @property
  def tbm_options(self):
    return self._tbm_options
