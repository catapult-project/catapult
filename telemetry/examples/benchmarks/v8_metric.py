# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.value import improvement_direction
from telemetry.value import scalar
from telemetry.web_perf.metrics import timeline_based_metric

def _IsMessageLoopEvent(event):
  return event.name.startswith('v8')


class _AverageMessageLoopLatency(scalar.ScalarValue):
  def __init__(self, value, page, tir_label, none_value_reason=None):
    super(_AverageMessageLoopLatency, self).__init__(
      page=page, name='avg_v8_events_latency', value=value,
      tir_label=tir_label,
      units='ms', improvement_direction=improvement_direction.DOWN,
      description=('Average wall-time latency of message loop events during '
                   'any of the interaction records\' time ranges'),
      none_value_reason=none_value_reason)


class MessageLoopLatencyMetric(timeline_based_metric.TimelineBasedMetric):

  def AddResults(self, model, renderer_thread, interactions, results):
    v8_events = []
    for event in model.IterAllEvents(event_predicate=_IsMessageLoopEvent):
      if timeline_based_metric.IsEventInInteractions(event, interactions):
        v8_events.append(event)

    if v8_events:
      avg = (
          sum(e.duration for e in v8_events)/len(v8_events))
      results.AddValue(_AverageMessageLoopLatency(
          value=avg, page=results.current_page,
          tir_label=interactions[0].label))
    else:
      results.AddValue(_AverageMessageLoopLatency(
          None, page=results.current_page,
          tir_label=interactions[0].label,
          none_value_reason='No v8 events found.'))
