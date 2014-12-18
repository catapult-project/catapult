# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math
from telemetry.value import scalar
from telemetry.web_perf.metrics import timeline_based_metric


class LayoutMetric(timeline_based_metric.TimelineBasedMetric):
  """Computes metrics that measure layout performance, specifically,
  avg and stddev of CPU time of layout-related trace events:

    layout_total_{avg,stddev}: FrameView::layout
    layout_{avg,stddev}: FrameView::performLayout
    pre_layout_{avg,stddev}: FrameView::performPreLayoutTasks
    post_layout_{avg,stddev}: FrameView::performPostLayoutTasks
    layer_positions_{avg,stddev}: RenderLayer::updateLayerPositionsAfterLayout

  Layout happens no more than once per frame, so per-frame-ness is implied.
  Not all pages have interactions, so interaction records are not required.
  """
  EVENTS = {
    'FrameView::layout': 'layout_total',
    'FrameView::performLayout': 'layout',
    'FrameView::performPreLayoutTasks': 'pre_layout',
    'FrameView::performPostLayoutTasks': 'post_layout',
    'RenderLayer::updateLayerPositionsAfterLayout': 'layer_positions',
  }

  def __init__(self):
    super(LayoutMetric, self).__init__()

  def AddResults(self, _model, renderer_thread, _interaction_records, results):
    self._AddResults(renderer_thread.parent.IterAllSlices(), results)

  def _AddResults(self, events, results):
    metrics = dict((long_name, (short_name, [])) for long_name, short_name in
        self.EVENTS.iteritems())

    for event in events:
      if event.name in metrics:
        metrics[event.name][1].append(event.end - event.start)

    for long_name, (short_name, durations) in metrics.iteritems():
      count = len(durations)
      avg = 0.0
      stddev = 0.0
      if count:
        avg = sum(durations) / count
        stddev = math.sqrt(sum((d - avg) ** 2 for d in durations) / count)
      results.AddValue(scalar.ScalarValue(results.current_page,
          short_name + '_avg', 'ms', avg,
          description='Average duration of %s events' % long_name))
      results.AddValue(scalar.ScalarValue(results.current_page,
          short_name + '_stddev', 'ms', stddev,
          description='stddev of duration of %s events' % long_name))
