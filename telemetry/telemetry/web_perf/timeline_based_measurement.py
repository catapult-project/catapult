# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from collections import defaultdict
from telemetry.core import util
from telemetry.core.platform import tracing_category_filter
from telemetry.timeline import model as model_module
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import fast_metric
from telemetry.web_perf.metrics import responsiveness_metric
from telemetry.web_perf.metrics import smoothness
from telemetry.page import page_test
from telemetry.value import string as string_value_module


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


class InvalidInteractions(Exception):
  pass


def _GetMetricFromMetricType(metric_type):
  if metric_type == tir_module.IS_FAST:
    return fast_metric.FastMetric()
  if metric_type == tir_module.IS_SMOOTH:
    return smoothness.SmoothnessMetric()
  if metric_type == tir_module.IS_RESPONSIVE:
    return responsiveness_metric.ResponsivenessMetric()
  raise Exception('Unrecognized metric type: %s' % metric_type)


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

class _TimelineBasedMetrics(object):
  def __init__(self, model, renderer_thread,
               get_metric_from_metric_type_callback):
    self._model = model
    self._renderer_thread = renderer_thread
    self._get_metric_from_metric_type_callback = \
        get_metric_from_metric_type_callback

  def FindTimelineInteractionRecords(self):
    # TODO(nduca): Add support for page-load interaction record.
    return [tir_module.TimelineInteractionRecord.FromAsyncEvent(event) for
            event in self._renderer_thread.async_slices
            if tir_module.IsTimelineInteractionRecord(event.name)]

  def AddResults(self, results):
    all_interactions = self.FindTimelineInteractionRecords()
    if len(all_interactions) == 0:
      raise InvalidInteractions('Expected at least one interaction record on '
                                'the page')

    interactions_by_label = defaultdict(list)
    for i in all_interactions:
      interactions_by_label[i.label].append(i)

    for label, interactions in interactions_by_label.iteritems():
      are_repeatable = [i.repeatable for i in interactions]
      if not all(are_repeatable) and len(interactions) > 1:
        raise InvalidInteractions('Duplicate unrepeatable interaction records '
                                  'on the page')
      wrapped_results = _ResultsWrapper(results, label)
      self.UpdateResultsByMetric(interactions, wrapped_results)

  def UpdateResultsByMetric(self, interactions, wrapped_results):
    for metric_type in tir_module.METRICS:
      # For each metric type, either all or none of the interactions should
      # have that metric.
      interactions_with_metric = [i for i in interactions if
                                  i.HasMetric(metric_type)]
      if not interactions_with_metric:
        continue
      if len(interactions_with_metric) != len(interactions):
        raise InvalidInteractions('Interaction records with the same logical '
                                  'name must have the same flags.')
      metric = self._get_metric_from_metric_type_callback(metric_type)
      metric.AddResults(self._model, self._renderer_thread,
                        interactions, wrapped_results)


class TimelineBasedMeasurement(page_test.PageTest):
  """Collects multiple metrics pages based on their interaction records.

  A timeline measurement shifts the burden of what metrics to collect onto the
  page under test, or the pageset running that page. Instead of the measurement
  having a fixed set of values it collects about the page, the page being tested
  issues (via javascript) an Interaction record into the user timing API that
  describing what the page is doing at that time, as well as a standardized set
  of flags describing the semantics of the work being done. The
  TimelineBasedMeasurement object collects a trace that includes both these
  interaction recorsd, and a user-chosen amount of performance data using
  Telemetry's various timeline-producing APIs, tracing especially.

  It then passes the recorded timeline to different TimelineBasedMetrics based
  on those flags. This allows a single run through a page to produce load timing
  data, smoothness data, critical jank information and overall cpu usage
  information.

  For information on how to mark up a page to work with
  TimelineBasedMeasurement, refer to the
  perf.metrics.timeline_interaction_record module.

  """
  def __init__(self):
    super(TimelineBasedMeasurement, self).__init__('RunSmoothness')

  @classmethod
  def AddCommandLineArgs(cls, parser):
    parser.add_option(
        '--overhead-level', dest='overhead_level', type='choice',
        choices=ALL_OVERHEAD_LEVELS,
        default=NO_OVERHEAD_LEVEL,
        help='How much overhead to incur during the measurement.')
    parser.add_option(
        '--trace-dir', dest='trace_dir', type='string', default=None,
        help=('Where to save the trace after the run. If this flag '
              'is not set, the trace will not be saved.'))

  def WillNavigateToPage(self, page, tab):
    if not tab.browser.supports_tracing:
      raise Exception('Not supported')

    assert self.options.overhead_level in ALL_OVERHEAD_LEVELS
    if self.options.overhead_level == NO_OVERHEAD_LEVEL:
      category_filter = tracing_category_filter.CreateNoOverheadFilter()
    elif self.options.overhead_level == MINIMAL_OVERHEAD_LEVEL:
      category_filter = tracing_category_filter.CreateMinimalOverheadFilter()
    else:
      category_filter = tracing_category_filter.CreateDebugOverheadFilter()

    for delay in page.GetSyntheticDelayCategories():
      category_filter.AddSyntheticDelay(delay)

    tab.browser.StartTracing(category_filter)

  def ValidateAndMeasurePage(self, page, tab, results):
    """ Collect all possible metrics and added them to results. """
    trace_result = tab.browser.StopTracing()
    trace_dir = self.options.trace_dir
    if trace_dir:
      trace_file_path = util.GetSequentialFileName(
          os.path.join(trace_dir, 'trace')) + '.json'
      try:
        with open(trace_file_path, 'w') as f:
          trace_result.Serialize(f)
        results.AddValue(string_value_module.StringValue(
            page, 'trace_path', 'string', trace_file_path))
      except IOError, e:
        logging.error('Cannot open %s. %s' % (trace_file_path, e))

    model = model_module.TimelineModel(trace_result)
    renderer_thread = model.GetRendererThreadFromTabId(tab.id)
    meta_metrics = _TimelineBasedMetrics(
        model, renderer_thread, _GetMetricFromMetricType)
    meta_metrics.AddResults(results)

  def CleanUpAfterPage(self, page, tab):
    if tab.browser.is_tracing_running:
      tab.browser.StopTracing()
