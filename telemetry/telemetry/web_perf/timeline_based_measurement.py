# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from telemetry.core import util
from telemetry.core.backends.chrome import tracing_backend
from telemetry.timeline import model as model_module
from telemetry.web_perf import timeline_interaction_record as tir_module
from telemetry.web_perf.metrics import smoothness
from telemetry.web_perf.metrics import responsiveness_metric
from telemetry.page import page_measurement
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


class _ResultsWrapper(object):
  def __init__(self, results, interaction_record):
    self._results = results
    self._interaction_record = interaction_record

  def Add(self, trace_name, units, value, chart_name=None, data_type='default'):
    trace_name = self._interaction_record.GetResultNameFor(trace_name)
    self._results.Add(trace_name, units, value, chart_name, data_type)

  def AddSummary(self, trace_name, units, value, chart_name=None,
                  data_type='default'):
    trace_name = self._interaction_record.GetResultNameFor(trace_name)
    self._results.AddSummary(trace_name, units, value, chart_name, data_type)


class _TimelineBasedMetrics(object):
  def __init__(self, model, renderer_thread,
               create_metrics_for_interaction_record_callback):
    self._model = model
    self._renderer_thread = renderer_thread
    self._create_metrics_for_interaction_record_callback = \
        create_metrics_for_interaction_record_callback

  def FindTimelineInteractionRecords(self):
    # TODO(nduca): Add support for page-load interaction record.
    return [tir_module.TimelineInteractionRecord.FromAsyncEvent(event) for
            event in self._renderer_thread.async_slices
            if tir_module.IsTimelineInteractionRecord(event.name)]

  def AddResults(self, results):
    interactions = self.FindTimelineInteractionRecords()
    if len(interactions) == 0:
      raise Exception('Expected at least one Interaction on the page')
    for interaction in interactions:
      metrics = \
          self._create_metrics_for_interaction_record_callback(interaction)
      wrapped_results = _ResultsWrapper(results, interaction)
      for m in metrics:
        m.AddResults(self._model, self._renderer_thread,
                     [interaction], wrapped_results)


class TimelineBasedMeasurement(page_measurement.PageMeasurement):
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
      categories = tracing_backend.MINIMAL_TRACE_CATEGORIES
    elif self.options.overhead_level == \
        MINIMAL_OVERHEAD_LEVEL:
      categories = ''
    else:
      categories = '*,disabled-by-default-cc.debug'
    categories = ','.join([categories] + page.GetSyntheticDelayCategories())
    tab.browser.StartTracing(categories)

  def CreateMetricsForTimelineInteractionRecord(self, interaction):
    """ Subclass of TimelineBasedMeasurement overrides this method to customize
    the binding of interaction's flags to metrics.
    """
    res = []
    if interaction.is_smooth:
      res.append(smoothness.SmoothnessMetric())
    if interaction.is_responsive:
      res.append(responsiveness_metric.ResponsivenessMetric())
    return res

  def MeasurePage(self, page, tab, results):
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
      model, renderer_thread, self.CreateMetricsForTimelineInteractionRecord)
    meta_metrics.AddResults(results)

  def CleanUpAfterPage(self, page, tab):
    if tab.browser.is_tracing_running:
      tab.browser.StopTracing()

  @property
  def results_are_the_same_on_every_page(self):
    return False
