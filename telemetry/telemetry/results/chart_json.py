# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import itertools

from telemetry.value import summary as summary_module

def ResultsAsChartDict(benchmark_metadata, page_specific_values,
                       summary_values):
  """Produces a dict for serialization to Chart JSON format from raw values.

  Chart JSON is a transformation of the basic Telemetry JSON format that
  removes the page map, summarizes the raw values, and organizes the results
  by chart and trace name. This function takes the key pieces of data needed to
  perform this transformation (namely, lists of values and a benchmark metadata
  object) and processes them into a dict which can be serialized using the json
  module.

  Design doc for schema: http://goo.gl/kOtf1Y

  Args:
    page_specific_values: list of page-specific values
    summary_values: list of summary values
    benchmark_metadata: a benchmark.BenchmarkMetadata object

  Returns:
    A Chart JSON dict corresponding to the given data.
  """
  summary = summary_module.Summary(page_specific_values)
  values = itertools.chain(
      summary.interleaved_computed_per_page_values_and_summaries,
      summary_values)
  charts = collections.defaultdict(dict)

  for value in values:
    if value.page:
      chart_name, trace_name = (
          value.GetChartAndTraceNameForPerPageResult())
    else:
      chart_name, trace_name = (
          value.GetChartAndTraceNameForComputedSummaryResult(None))
      if chart_name == trace_name:
        trace_name = 'summary'

    assert trace_name not in charts[chart_name]

    charts[chart_name][trace_name] = value.AsDict()

  result_dict = {
    'format_version': '0.1',
    'benchmark_name': benchmark_metadata.name,
    'charts': charts
  }

  return result_dict
