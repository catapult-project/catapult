# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.web_perf.metrics import timeline_based_metric


class SmoothnessMetric(timeline_based_metric.TimelineBasedMetric):
  """Computes metrics that measure smoothness of animations over given ranges.

  These metrics now live in tracing/metrics/rendering. This file exists only
  until the dependencies to it from the chromium repository are removed.
  """

  def AddResults(self, model, renderer_thread, interaction_records, results):
    pass
