# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import itertools
import json
import os

from telemetry.internal.results import output_formatter
from telemetry.internal.results import results_processor


def _GetChartAndTraceName(value):
  # Telemetry names values using a chart_name.trace_name convention, wheras
  # chartjson uses a (measurement_name, trace_name) convention. This maps from
  # the Telemetry to the chartjson convention.
  if '.' in value.name:
    chart_name, trace_name = value.name.split('.')
  else:
    chart_name, trace_name = value.name, value.name
  if value.page:
    trace_name = value.page.name  # Summary values for a single page.
  elif chart_name == trace_name:
    trace_name = 'summary'  # Summary values for a metric on all pages.

  # Dashboard handles the chart_name of trace values specially: it
  # strips out the field with chart_name 'trace'. Hence in case trace
  # value has grouping_label, we preserve the chart_name.
  # For relevant section code of dashboard code that handles this, see:
  # https://github.com/catapult-project/catapult/blob/25e660b/dashboard/dashboard/add_point.py#L199#L216
  if value.grouping_label:
    chart_name = value.grouping_label + '@@' + chart_name

  return chart_name, trace_name


def ResultsAsChartDict(results):
  """Produces a dict for serialization to Chart JSON format from raw values.

  Chart JSON is a transformation of the basic Telemetry JSON format that
  removes the page map, summarizes the raw values, and organizes the results
  by chart and trace name. This function takes the key pieces of data needed to
  perform this transformation and processes them into a dict which can be
  serialized using the json module.

  Design doc for schema: http://goo.gl/kOtf1Y

  Args:
    results: an instance of PageTestResults

  Returns:
    A Chart JSON dict corresponding to the given data.
  """
  values = itertools.chain(
      output_formatter.SummarizePageSpecificValues(results),
      results.all_summary_values)
  charts = collections.defaultdict(dict)

  for value in values:
    chart_name, trace_name = _GetChartAndTraceName(value)

    # This intentionally overwrites the trace if it already exists because this
    # is expected of output from the buildbots currently.
    # See: crbug.com/413393
    charts[chart_name][trace_name] = value.AsDict()
    if value.page:
      charts[chart_name][trace_name]['story_tags'] = list(value.page.tags)

  for run in results.IterStoryRuns():
    artifact = run.GetArtifact(results_processor.HTML_TRACE_NAME)
    if artifact is not None:
      # This intentionally overwrites the trace if it already exists because
      # this is expected of output from the buildbots currently.
      # See: crbug.com/413393
      charts['trace'][run.story.name] = {
          'name': 'trace',
          'type': 'trace',
          'units': '',
          'important': False,
          'page_id': run.story.id,
          'file_path': os.path.relpath(artifact.local_path, results.output_dir),
      }
      if artifact.url is not None:
        charts['trace'][run.story.name]['cloud_url'] = artifact.url

  result_dict = {
      'format_version': '0.1',
      'next_version': '0.2',
      # TODO(sullivan): benchmark_name and benchmark_description should be
      # removed when incrementing format_version to 0.1.
      'benchmark_name': results.benchmark_name,
      'benchmark_description': results.benchmark_description,
      'benchmark_metadata': {
          'type': 'telemetry_benchmark',
          'name': results.benchmark_name,
          'description': results.benchmark_description,
      },
      'charts': charts,
      # Conveys whether the whole benchmark was disabled.
      'enabled': not results.empty,
  }

  return result_dict


class ChartJsonOutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream):
    super(ChartJsonOutputFormatter, self).__init__(output_stream)

  def Format(self, results):
    self._Dump(ResultsAsChartDict(results))

  def _Dump(self, results):
    json.dump(results, self.output_stream, indent=2, separators=(',', ': '))
    self.output_stream.write('\n')
