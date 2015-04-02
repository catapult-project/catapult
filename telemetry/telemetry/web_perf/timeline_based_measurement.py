# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict

from telemetry.core.platform import tracing_category_filter
from telemetry.core.platform import tracing_options
from telemetry.timeline import model as model_module
from telemetry.value import trace
from telemetry.web_perf.metrics import layout
from telemetry.web_perf.metrics import responsiveness_metric
from telemetry.web_perf.metrics import smoothness
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
          layout.LayoutMetric())


class InvalidInteractions(Exception):
  pass


# TODO(nednguyen): Get rid of this results wrapper hack after we add interaction
# record to telemetry value system.
class _ResultsWrapper(object):
  def __init__(self, results, label):
    self._results = results
    self._result_prefix = label

  @property
  def current_page(self):
    return self._results.current_page

  def _GetResultName(self, trace_name):
    return '%s-%s' % (self._result_prefix, trace_name)

  def AddValue(self, value):
    value.name = self._GetResultName(value.name)
    self._results.AddValue(value)


def _GetRendererThreadsToInteractionRecordsMap(model):
  threads_to_records_map = defaultdict(list)
  interaction_labels_of_previous_threads = set()
  for curr_thread in model.GetAllThreads():
    for event in curr_thread.async_slices:
      # TODO(nduca): Add support for page-load interaction record.
      if tir_module.IsTimelineInteractionRecord(event.name):
        interaction = tir_module.TimelineInteractionRecord.FromAsyncEvent(event)
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
  def __init__(self, model, renderer_thread, interaction_records):
    self._model = model
    self._renderer_thread = renderer_thread
    self._interaction_records = interaction_records

  def AddResults(self, results):
    interactions_by_label = defaultdict(list)
    for i in self._interaction_records:
      interactions_by_label[i.label].append(i)

    for label, interactions in interactions_by_label.iteritems():
      are_repeatable = [i.repeatable for i in interactions]
      if not all(are_repeatable) and len(interactions) > 1:
        raise InvalidInteractions('Duplicate unrepeatable interaction records '
                                  'on the page')
      wrapped_results = _ResultsWrapper(results, label)
      self.UpdateResultsByMetric(interactions, wrapped_results)

  def UpdateResultsByMetric(self, interactions, wrapped_results):
    if not interactions:
      return

    for metric in _GetAllTimelineBasedMetrics():
      metric.AddResults(self._model, self._renderer_thread,
                        interactions, wrapped_results)


class Options(object):
  """A class to be used to configure TimelineBasedMeasurement.

  This is created and returned by
  Benchmark.CreateTimelineBasedMeasurementOptions.
  """

  def __init__(self, overhead_level=NO_OVERHEAD_LEVEL):
    """As the amount of instrumentation increases, so does the overhead.
    The user of the measurement chooses the overhead level that is appropriate,
    and the tracing is filtered accordingly.

    overhead_level: Can either be a custom TracingCategoryFilter object or
        one of NO_OVERHEAD_LEVEL, MINIMAL_OVERHEAD_LEVEL or
        DEBUG_OVERHEAD_LEVEL.
    """
    if (not isinstance(overhead_level,
                       tracing_category_filter.TracingCategoryFilter) and
        overhead_level not in ALL_OVERHEAD_LEVELS):
      raise Exception("Overhead level must be a TracingCategoryFilter object"
                      " or valid overhead level string."
                      " Given overhead level: %s" % overhead_level)

    self._overhead_level = overhead_level
    self._extra_category_filters = []

  def ExtendTraceCategoryFilters(self, filters):
    self._extra_category_filters.extend(filters)

  @property
  def extra_category_filters(self):
    return self._extra_category_filters

  @property
  def overhead_level(self):
    return self._overhead_level


class TimelineBasedMeasurement(object):
  """Collects multiple metrics based on their interaction records.

  A timeline based measurement shifts the burden of what metrics to collect onto
  the user story under test. Instead of the measurement
  having a fixed set of values it collects, the user story being tested
  issues (via javascript) an Interaction record into the user timing API that
  describing what is happening at that time, as well as a standardized set
  of flags describing the semantics of the work being done. The
  TimelineBasedMeasurement object collects a trace that includes both these
  interaction records, and a user-chosen amount of performance data using
  Telemetry's various timeline-producing APIs, tracing especially.

  It then passes the recorded timeline to different TimelineBasedMetrics based
  on those flags. As an example, this allows a single user story run to produce
  load timing data, smoothness data, critical jank information and overall cpu
  usage information.

  For information on how to mark up a page to work with
  TimelineBasedMeasurement, refer to the
  perf.metrics.timeline_interaction_record module.
  """
  def __init__(self, options):
    self._tbm_options = options

  def WillRunUserStory(self, tracing_controller,
                       synthetic_delay_categories=None):
    """Configure and start tracing.

    Args:
      app: an app.App subclass instance.
      synthetic_delay_categories: iterable of delays. For example:
          ['DELAY(cc.BeginMainFrame;0.014;alternating)']
          where 'cc.BeginMainFrame' is a timeline event, 0.014 is the delay,
          and 'alternating' is the mode.
    """
    if not tracing_controller.IsChromeTracingSupported():
      raise Exception('Not supported')

    if isinstance(self._tbm_options.overhead_level,
                  tracing_category_filter.TracingCategoryFilter):
      category_filter = self._tbm_options.overhead_level
    else:
      assert self._tbm_options.overhead_level in ALL_OVERHEAD_LEVELS, (
          "Invalid TBM Overhead Level: %s" % self._tbm_options.overhead_level)

      if self._tbm_options.overhead_level == NO_OVERHEAD_LEVEL:
        category_filter = tracing_category_filter.CreateNoOverheadFilter()
      elif self._tbm_options.overhead_level == MINIMAL_OVERHEAD_LEVEL:
        category_filter = tracing_category_filter.CreateMinimalOverheadFilter()
      else:
        category_filter = tracing_category_filter.CreateDebugOverheadFilter()

    for new_category_filter in self._tbm_options.extra_category_filters:
      category_filter.AddIncludedCategory(new_category_filter)

    # TODO(slamm): Move synthetic_delay_categories to the TBM options.
    for delay in synthetic_delay_categories or []:
      category_filter.AddSyntheticDelay(delay)
    options = tracing_options.TracingOptions()
    options.enable_chrome_trace = True
    options.enable_platform_display_trace = True
    tracing_controller.Start(options, category_filter)

  def Measure(self, tracing_controller, results):
    """Collect all possible metrics and added them to results."""
    trace_result = tracing_controller.Stop()
    results.AddValue(trace.TraceValue(results.current_page, trace_result))
    model = model_module.TimelineModel(trace_result)
    threads_to_records_map = _GetRendererThreadsToInteractionRecordsMap(model)
    for renderer_thread, interaction_records in (
        threads_to_records_map.iteritems()):
      meta_metrics = _TimelineBasedMetrics(
          model, renderer_thread, interaction_records)
      meta_metrics.AddResults(results)

  def DidRunUserStory(self, tracing_controller):
    if tracing_controller.is_tracing_running:
      tracing_controller.Stop()
