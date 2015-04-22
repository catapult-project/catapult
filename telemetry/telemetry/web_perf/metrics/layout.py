# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.value import list_of_scalar_values
from telemetry.web_perf.metrics import timeline_based_metric


class LayoutMetric(timeline_based_metric.TimelineBasedMetric):
  """Reports directly durations of FrameView::performLayout events.

    layout: Durations of FrameView::performLayout events that were caused by and
            start during user interaction.

  Layout happens no more than once per frame, so per-frame-ness is implied.
  """
  EVENT_NAME = 'FrameView::performLayout'

  def __init__(self):
    super(LayoutMetric, self).__init__()

  def AddResults(self, _model, renderer_thread, interactions, results):
    assert interactions
    self._AddResultsInternal(renderer_thread.parent.IterAllSlices(),
                             interactions, results)

  def _AddResultsInternal(self, events, interactions, results):
    layouts = []
    for event in events:
      if (event.name == self.EVENT_NAME) and any(
              interaction.start <= event.start <= interaction.end
              for interaction in interactions):
        layouts.append(event.end - event.start)
    if not layouts:
      return
    results.AddValue(list_of_scalar_values.ListOfScalarValues(
      page=results.current_page,
      name='layout',
      units='ms',
      values=layouts,
      description=('List of durations of layouts that were caused by and '
                   'start during interactions')))
