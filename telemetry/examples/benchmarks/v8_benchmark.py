# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry import benchmark
from telemetry.timeline import tracing_category_filter
from telemetry.web_perf import timeline_based_measurement

from benchmarks import simple_story_set
from benchmarks import v8_metric


class MessageLoopBenchmark(benchmark.Benchmark):

  def CreateStorySet(self, options):
    return simple_story_set.SimpleStorySet()

  def CreateTimelineBasedMeasurementOptions(self):
    cat_filter = tracing_category_filter.CreateNoOverheadFilter()
    # blink.console category is required to make sure that Chrome can output
    # interaction records in its tracing data.
    cat_filter.AddIncludedCategory('blink.console')
    cat_filter.AddIncludedCategory('v8')
    options = timeline_based_measurement.Options(overhead_level=cat_filter)
    options.SetTimelineBasedMetrics(
        [v8_metric.MessageLoopLatencyMetric()])
    return options

  @classmethod
  def Name(cls):
    return 'v8_latency.simple_story'
