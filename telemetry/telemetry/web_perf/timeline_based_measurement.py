# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import collections
import logging
from collections import defaultdict

from telemetry.timeline import model as model_module
from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_options
from telemetry.value import trace
from telemetry.web_perf.metrics import timeline_based_metric
from telemetry.web_perf.metrics import blob_timeline
from telemetry.web_perf.metrics import webrtc_rendering_timeline
from telemetry.web_perf.metrics import gpu_timeline
from telemetry.web_perf.metrics import indexeddb_timeline
from telemetry.web_perf.metrics import layout
from telemetry.web_perf.metrics import memory_timeline
from telemetry.web_perf.metrics import responsiveness_metric
from telemetry.web_perf.metrics import smoothness
from telemetry.web_perf.metrics import text_selection
from telemetry.web_perf import smooth_gesture_util
from telemetry.web_perf import story_test
from telemetry.web_perf import timeline_interaction_record as tir_module

# TimelineBasedMeasurement considers all instrumentation as producing a single
# timeline. But, depending on the amount of instrumentation that is enabled,
# overhead increases. The user of the measurement must therefore chose between
# a few levels of instrumentation.
NO_OVERHEAD_LEVEL = 'no-overhead'
MINIMAL_OVERHEAD_LEVEL = 'minimal-overhead'
DEBUG_OVERHEAD_LEVEL = 'debug-overhead'

ALL_OVERHEAD_LEVELS = [
  NO_OVERHEAD_LEVEL,
  MINIMAL_OVERHEAD_LEVEL,
  DEBUG_OVERHEAD_LEVEL
]


def _GetAllTimelineBasedMetrics():
  # TODO(nednguyen): use discovery pattern to return all the instances of
  # all TimelineBasedMetrics class in web_perf/metrics/ folder.
  # This cannot be done until crbug.com/460208 is fixed.
  return (smoothness.SmoothnessMetric(),
          responsiveness_metric.ResponsivenessMetric(),
          layout.LayoutMetric(),
          gpu_timeline.GPUTimelineMetric(),
          blob_timeline.BlobTimelineMetric(),
          memory_timeline.MemoryTimelineMetric(),
          text_selection.TextSelectionMetric(),
          indexeddb_timeline.IndexedDBTimelineMetric(),
          webrtc_rendering_timeline.WebRtcRenderingTimelineMetric())


class InvalidInteractions(Exception):
  pass


# TODO(nednguyen): Get rid of this results wrapper hack after we add interaction
# record to telemetry value system (crbug.com/453109)
class ResultsWrapperInterface(object):
  def __init__(self):
    self._tir_label = None
    self._results = None

  def SetResults(self, results):
    self._results = results

  def SetTirLabel(self, tir_label):
    self._tir_label = tir_label

  @property
  def current_page(self):
    return self._results.current_page

  def AddValue(self, value):
    raise NotImplementedError


class _TBMResultWrapper(ResultsWrapperInterface):
  def AddValue(self, value):
    assert self._tir_label
    if value.tir_label:
      assert value.tir_label == self._tir_label
    else:
      logging.warning(
          'TimelineBasedMetric should create the interaction record label '
          'for the value themselves. Value: %s' % repr(value))
      value.tir_label = self._tir_label
    self._results.AddValue(value)


def _GetRendererThreadsToInteractionRecordsMap(model):
  threads_to_records_map = defaultdict(list)
  interaction_labels_of_previous_threads = set()
  for curr_thread in model.GetAllThreads():
    for event in curr_thread.async_slices:
      # TODO(nduca): Add support for page-load interaction record.
      if tir_module.IsTimelineInteractionRecord(event.name):
        interaction = tir_module.TimelineInteractionRecord.FromAsyncEvent(event)
        # Adjust the interaction record to match the synthetic gesture
        # controller if needed.
        interaction = (
            smooth_gesture_util.GetAdjustedInteractionIfContainGesture(
                model, interaction))
        threads_to_records_map[curr_thread].append(interaction)
        if interaction.label in interaction_labels_of_previous_threads:
          raise InvalidInteractions(
            'Interaction record label %s is duplicated on different '
            'threads' % interaction.label)
    if curr_thread in threads_to_records_map:
      interaction_labels_of_previous_threads.update(
        r.label for r in threads_to_records_map[curr_thread])

  return threads_to_records_map


class _TimelineBasedMetrics(object):
  def __init__(self, model, renderer_thread, interaction_records,
               results_wrapper, metrics):
    self._model = model
    self._renderer_thread = renderer_thread
    self._interaction_records = interaction_records
    self._results_wrapper = results_wrapper
    self._all_metrics = metrics

  def AddResults(self, results):
    interactions_by_label = defaultdict(list)
    for i in self._interaction_records:
      interactions_by_label[i.label].append(i)

    for label, interactions in interactions_by_label.iteritems():
      are_repeatable = [i.repeatable for i in interactions]
      if not all(are_repeatable) and len(interactions) > 1:
        raise InvalidInteractions('Duplicate unrepeatable interaction records '
                                  'on the page')
      self._results_wrapper.SetResults(results)
      self._results_wrapper.SetTirLabel(label)
      self.UpdateResultsByMetric(interactions, self._results_wrapper)

  def UpdateResultsByMetric(self, interactions, wrapped_results):
    if not interactions:
      return

    for metric in self._all_metrics:
      metric.AddResults(self._model, self._renderer_thread,
                        interactions, wrapped_results)


class Options(object):
  """A class to be used to configure TimelineBasedMeasurement.

  This is created and returned by
  Benchmark.CreateTimelineBasedMeasurementOptions.

  By default, all the timeline based metrics in telemetry/web_perf/metrics are
  used (see _GetAllTimelineBasedMetrics above).
  To customize your metric needs, use SetTimelineBasedMetrics().
  """

  def __init__(self, overhead_level=NO_OVERHEAD_LEVEL):
    """As the amount of instrumentation increases, so does the overhead.
    The user of the measurement chooses the overhead level that is appropriate,
    and the tracing is filtered accordingly.

    overhead_level: Can either be a custom TracingCategoryFilter object or
        one of NO_OVERHEAD_LEVEL, MINIMAL_OVERHEAD_LEVEL or
        DEBUG_OVERHEAD_LEVEL.
    """
    self._category_filter = None
    if isinstance(overhead_level,
                  tracing_category_filter.TracingCategoryFilter):
      self._category_filter = overhead_level
    elif overhead_level in ALL_OVERHEAD_LEVELS:
      if overhead_level == NO_OVERHEAD_LEVEL:
        self._category_filter = tracing_category_filter.CreateNoOverheadFilter()
      elif overhead_level == MINIMAL_OVERHEAD_LEVEL:
        self._category_filter = (
          tracing_category_filter.CreateMinimalOverheadFilter())
      else:
        self._category_filter = (
          tracing_category_filter.CreateDebugOverheadFilter())
    else:
      raise Exception("Overhead level must be a TracingCategoryFilter object"
                      " or valid overhead level string."
                      " Given overhead level: %s" % overhead_level)

    self._tracing_options = tracing_options.TracingOptions()
    self._tracing_options.enable_chrome_trace = True
    self._tracing_options.enable_platform_display_trace = True
    self._timeline_based_metrics = _GetAllTimelineBasedMetrics()


  def ExtendTraceCategoryFilter(self, filters):
    for new_category_filter in filters:
      self._category_filter.AddIncludedCategory(new_category_filter)

  @property
  def category_filter(self):
    return self._category_filter

  @property
  def tracing_options(self):
    return self._tracing_options

  @tracing_options.setter
  def tracing_options(self, value):
    self._tracing_options = value

  def SetTimelineBasedMetrics(self, metrics):
    assert isinstance(metrics, collections.Iterable)
    for m in metrics:
      assert isinstance(m, timeline_based_metric.TimelineBasedMetric)
    self._timeline_based_metrics = metrics

  def GetTimelineBasedMetrics(self):
    return self._timeline_based_metrics


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

  For information on how to mark up a page to work with
  TimelineBasedMeasurement, refer to the
  perf.metrics.timeline_interaction_record module.

  Args:
      options: an instance of timeline_based_measurement.Options.
      results_wrapper: A class that has the __init__ method takes in
        the page_test_results object and the interaction record label. This
        class follows the ResultsWrapperInterface. Note: this class is not
        supported long term and to be removed when crbug.com/453109 is resolved.
  """
  def __init__(self, options, results_wrapper=None):
    self._tbm_options = options
    self._results_wrapper = results_wrapper or _TBMResultWrapper()

  def WillRunStory(self, platform):
    """Configure and start tracing."""
    if not platform.tracing_controller.IsChromeTracingSupported():
      raise Exception('Not supported')
    platform.tracing_controller.Start(self._tbm_options.tracing_options,
                                      self._tbm_options.category_filter)

  def Measure(self, platform, results):
    """Collect all possible metrics and added them to results."""
    trace_result = platform.tracing_controller.Stop()
    results.AddValue(trace.TraceValue(results.current_page, trace_result))
    model = model_module.TimelineModel(trace_result)
    threads_to_records_map = _GetRendererThreadsToInteractionRecordsMap(model)
    if (len(threads_to_records_map.values()) == 0 and
        self._tbm_options.tracing_options.enable_chrome_trace):
      raise story_test.Failure(
          'No timeline interaction records were recorded in the trace. '
          'This could be caused by console.time() & console.timeEnd() execution'
          ' failure or the tracing category specified doesn\'t include '
          'blink.console categories.')
    for renderer_thread, interaction_records in (
        threads_to_records_map.iteritems()):
      meta_metrics = _TimelineBasedMetrics(
          model, renderer_thread, interaction_records,
          self._results_wrapper, self._tbm_options.GetTimelineBasedMetrics())
      meta_metrics.AddResults(results)

  def DidRunStory(self, platform):
    """Clean up after running the story."""
    if platform.tracing_controller.is_tracing_running:
      platform.tracing_controller.Stop()
