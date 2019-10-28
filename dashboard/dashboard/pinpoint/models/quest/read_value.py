# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import json
import logging
import ntpath
import posixpath

from dashboard.common import histogram_helpers
from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest
from dashboard.services import isolate
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic_ref
from tracing.value.diagnostics import reserved_infos


class ReadHistogramsJsonValue(quest.Quest):

  def __init__(self, results_filename, hist_name=None,
               grouping_label=None, story=None, statistic=None):
    self._results_filename = results_filename
    self._hist_name = hist_name
    self._grouping_label = grouping_label
    self._story = story
    self._statistic = statistic

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._results_filename == other._results_filename and
            self._hist_name == other._hist_name and
            self._grouping_label == other._grouping_label and
            self._story == other._story and
            self._statistic == other._statistic)

  def __str__(self):
    return 'Get results'

  @property
  def metric(self):
    return self._hist_name

  def Start(self, change, isolate_server, isolate_hash):
    del change

    return _ReadHistogramsJsonValueExecution(
        self._results_filename, self._hist_name, self._grouping_label,
        self._story, self._statistic, isolate_server, isolate_hash)

  @classmethod
  def FromDict(cls, arguments):
    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')
    if IsWindows(arguments):
      results_filename = ntpath.join(benchmark, 'perf_results.json')
    else:
      results_filename = posixpath.join(benchmark, 'perf_results.json')

    chart = arguments.get('chart')
    # TODO(crbug.com/974237): Only read from 'grouping_label' when enough time
    # has passed and clients no longer write the 'tir_label' only.
    grouping_label = (arguments.get('grouping_label') or
                      arguments.get('tir_label'))
    trace = arguments.get('trace')
    statistic = arguments.get('statistic')

    return cls(results_filename, chart, grouping_label, trace, statistic)


class _ReadHistogramsJsonValueExecution(execution.Execution):

  def __init__(self, results_filename, hist_name, grouping_label,
               story, statistic, isolate_server, isolate_hash):
    super(_ReadHistogramsJsonValueExecution, self).__init__()
    self._results_filename = results_filename
    self._hist_name = hist_name
    self._grouping_label = grouping_label
    self._story = story
    self._statistic = statistic
    self._isolate_server = isolate_server
    self._isolate_hash = isolate_hash

    self._trace_urls = []

  def _AsDict(self):
    return [{
        'key': 'trace',
        'value': trace_url['name'],
        'url': trace_url['url'],
    } for trace_url in self._trace_urls]

  def _Poll(self):
    histogram_dicts = RetrieveOutputJson(
        self._isolate_server, self._isolate_hash, self._results_filename)
    histograms = histogram_set.HistogramSet()
    histograms.ImportDicts(histogram_dicts)

    histograms_by_path = CreateHistogramSetByTestPathDict(histograms)
    self._trace_urls = FindTraceUrls(histograms)

    test_path_to_match = histogram_helpers.ComputeTestPathFromComponents(
        self._hist_name, grouping_label=self._grouping_label,
        story_name=self._story)
    logging.debug('Test path to match: %s', test_path_to_match)

    # Have to pull out either the raw sample values, or the statistic
    result_values = ExtractValuesFromHistograms(test_path_to_match,
                                                histograms_by_path,
                                                self._hist_name,
                                                self._grouping_label,
                                                self._story,
                                                self._statistic)

    self._Complete(result_values=tuple(result_values))


def ExtractValuesFromHistograms(test_path_to_match, histograms_by_path,
                                histogram_name, grouping_label, story,
                                statistic):
  result_values = []
  matching_histograms = []
  if test_path_to_match in histograms_by_path:
    matching_histograms = histograms_by_path.get(test_path_to_match, [])

    logging.debug('Found %s matching histograms', len(matching_histograms))

    for h in matching_histograms:
      result_values.extend(_GetValuesOrStatistic(statistic, h))
  elif histogram_name:
    # Histograms don't exist, which means this is summary
    summary_value = []
    for test_path, histograms_for_test_path in histograms_by_path.items():
      if test_path.startswith(test_path_to_match):
        for h in histograms_for_test_path:
          summary_value.extend(_GetValuesOrStatistic(statistic, h))
          matching_histograms.append(h)

    logging.debug('Found %s matching summary histograms',
                  len(matching_histograms))
    if summary_value:
      result_values.append(sum(summary_value))

    logging.debug('result values: %s', result_values)

  if not result_values and histogram_name:
    if matching_histograms:
      raise errors.ReadValueNoValues()
    else:
      conditions = {'histogram': histogram_name}
      if grouping_label:
        conditions['grouping_label'] = grouping_label
      if story:
        conditions['story'] = story
      reason = ', '.join(list(':'.join(i) for i in conditions.items()))
      raise errors.ReadValueNotFound(reason)
  return result_values


def CreateHistogramSetByTestPathDict(histograms):
  histograms_by_path = collections.defaultdict(list)

  for h in histograms:
    histograms_by_path[histogram_helpers.ComputeTestPath(h)].append(h)

  return histograms_by_path

def FindTraceUrls(histograms):
  # Get and cache any trace URLs.
  unique_trace_urls = set()
  for hist in histograms:
    trace_urls = hist.diagnostics.get(reserved_infos.TRACE_URLS.name)
    # TODO(simonhatch): Remove this sometime after May 2018. We had a
    # brief period where the histograms generated by tests had invalid
    # trace_urls diagnostics. If the diagnostic we get back is just a ref,
    # then skip.
    # https://github.com/catapult-project/catapult/issues/4243
    if trace_urls and not isinstance(
        trace_urls, diagnostic_ref.DiagnosticRef):
      unique_trace_urls.update(trace_urls)

  sorted_urls = sorted(unique_trace_urls)

  return [{'name': t.split('/')[-1], 'url': t} for t in sorted_urls]

def _GetValuesOrStatistic(statistic, hist):
  if not statistic:
    return hist.sample_values

  if not hist.sample_values:
    return []

  # TODO(simonhatch): Use Histogram.getStatisticScalar when it's ported from
  # js.
  if statistic == 'avg':
    return [hist.running.mean]
  elif statistic == 'min':
    return [hist.running.min]
  elif statistic == 'max':
    return [hist.running.max]
  elif statistic == 'sum':
    return [hist.running.sum]
  elif statistic == 'std':
    return [hist.running.stddev]
  elif statistic == 'count':
    return [hist.running.count]
  raise errors.ReadValueUnknownStat(statistic)


class ReadGraphJsonValue(quest.Quest):

  def __init__(self, results_filename, chart, trace):
    self._results_filename = results_filename
    self._chart = chart
    self._trace = trace

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._results_filename == other._results_filename and
            self._chart == other._chart and
            self._trace == other._trace)

  def __str__(self):
    return 'Get results'

  @property
  def metric(self):
    return self._chart

  def Start(self, change, isolate_server, isolate_hash):
    del change

    return _ReadGraphJsonValueExecution(
        self._results_filename, self._chart, self._trace,
        isolate_server, isolate_hash)

  @classmethod
  def FromDict(cls, arguments):
    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')
    if IsWindows(arguments):
      results_filename = ntpath.join(benchmark, 'perf_results.json')
    else:
      results_filename = posixpath.join(benchmark, 'perf_results.json')

    chart = arguments.get('chart')
    trace = arguments.get('trace')

    return cls(results_filename, chart, trace)


class _ReadGraphJsonValueExecution(execution.Execution):

  def __init__(
      self, results_filename, chart, trace, isolate_server, isolate_hash):
    super(_ReadGraphJsonValueExecution, self).__init__()
    self._results_filename = results_filename
    self._chart = chart
    self._trace = trace
    self._isolate_server = isolate_server
    self._isolate_hash = isolate_hash

  def _AsDict(self):
    return {'isolate_server': self._isolate_server}

  def _Poll(self):
    graphjson = RetrieveOutputJson(
        self._isolate_server, self._isolate_hash, self._results_filename)

    if not self._chart and not self._trace:
      self._Complete(result_values=tuple([]))
      return

    if self._chart not in graphjson:
      raise errors.ReadValueChartNotFound(self._chart)
    if self._trace not in graphjson[self._chart]['traces']:
      raise errors.ReadValueTraceNotFound(self._trace)
    result_value = float(graphjson[self._chart]['traces'][self._trace][0])

    self._Complete(result_values=(result_value,))


def IsWindows(arguments):
  dimensions = arguments.get('dimensions', ())
  if isinstance(dimensions, basestring):
    dimensions = json.loads(dimensions)
  for dimension in dimensions:
    if dimension['key'] == 'os' and dimension['value'].startswith('Win'):
      return True
  return False


def RetrieveOutputJson(isolate_server, isolate_hash, filename):
  logging.debug(
      'Retrieving json output (%s, %s, %s)',
      isolate_server, isolate_hash, filename)

  output_files = json.loads(isolate.Retrieve(
      isolate_server, isolate_hash))['files']
  logging.debug('response: %s', output_files)

  if filename not in output_files:
    if 'performance_browser_tests' not in filename:
      raise errors.ReadValueNoFile(filename)

    # TODO(simonhatch): Remove this once crbug.com/947501 is resolved.
    filename = filename.replace(
        'performance_browser_tests', 'browser_tests')
    if filename not in output_files:
      raise errors.ReadValueNoFile(filename)

  output_json_isolate_hash = output_files[filename]['h']
  logging.debug('Retrieving %s', output_json_isolate_hash)

  # TODO(dberris): Use incremental json parsing through a file interface, to
  # avoid having to load the whole string contents in memory. See
  # https://crbug.com/998517 for more context.
  response = json.loads(
      isolate.Retrieve(isolate_server, output_json_isolate_hash))
  logging.debug('response: %s', response)

  return response
