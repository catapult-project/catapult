# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.common import histogram_helpers
from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest
from dashboard.services import isolate
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic_ref
from tracing.value.diagnostics import reserved_infos


class ReadValueError(Exception):

  pass


class ReadChartJsonValue(quest.Quest):
  # TODO: Deprecated.

  def __init__(self, chart, tir_label=None, trace=None, statistic=None):
    self._chart = chart
    self._tir_label = tir_label
    self._trace = trace
    self._statistic = statistic

  # TODO: Remove this method after data migration.
  def __setstate__(self, state):
    # pylint: disable=attribute-defined-outside-init
    self.__dict__ = state

    if not hasattr(self, '_statistic'):
      self._statistic = None

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._chart == other._chart and
            self._tir_label == other._tir_label and
            self._trace == other._trace and
            self._statistic == other._statistic)

  def __str__(self):
    return 'Values'

  def Start(self, change, isolate_hash):
    del change
    return _ReadChartJsonValueExecution(self._chart, self._tir_label,
                                        self._trace, self._statistic,
                                        isolate_hash)

  @classmethod
  def FromDict(cls, arguments):
    chart = arguments.get('chart')
    tir_label = arguments.get('tir_label')
    trace = arguments.get('trace')
    statistic = arguments.get('statistic')
    return cls(chart, tir_label, trace, statistic)


class _ReadChartJsonValueExecution(execution.Execution):

  def __init__(self, chart, tir_label, trace, statistic, isolate_hash):
    super(_ReadChartJsonValueExecution, self).__init__()
    self._chart = chart
    self._tir_label = tir_label
    self._trace = trace
    self._isolate_hash = isolate_hash
    self._statistic = statistic

    self._trace_urls = []

  # TODO: Remove this method after data migration.
  def __setstate__(self, state):
    # pylint: disable=attribute-defined-outside-init
    self.__dict__ = state

    if not hasattr(self, '_statistic'):
      self._statistic = None

  def _AsDict(self):
    if not self._trace_urls:
      return {}
    return {'traces': self._trace_urls}

  def _Poll(self):
    chartjson = _RetrieveOutputJson(self._isolate_hash, 'chartjson-output.json')

    # Get and cache any trace URLs.
    unique_trace_urls = set()
    if 'trace' in chartjson['charts']:
      traces = chartjson['charts']['trace']
      traces = sorted(traces.iteritems(), key=lambda item: item[1]['page_id'])
      unique_trace_urls.update([d['cloud_url'] for _, d in traces])

    sorted_urls = sorted(unique_trace_urls)
    self._trace_urls = [
        {'name': t.split('/')[-1], 'url': t} for t in sorted_urls]

    # Look up chart.
    if self._tir_label:
      chart_name = '@@'.join((self._tir_label, self._chart))
    else:
      chart_name = self._chart

    if self._statistic:
      chart_name = '_'.join((chart_name, self._statistic))

    if chart_name not in chartjson['charts']:
      raise ReadValueError('The chart "%s" is not in the results.' % chart_name)

    # Look up trace.
    trace_name = self._trace or 'summary'
    if trace_name not in chartjson['charts'][chart_name]:
      raise ReadValueError('The trace "%s" is not in the results.' % trace_name)

    # Convert data to individual values.
    chart = chartjson['charts'][chart_name][trace_name]
    if chart['type'] == 'list_of_scalar_values':
      result_values = chart['values']
    elif chart['type'] == 'histogram':
      result_values = _ResultValuesFromHistogram(chart['buckets'])
    elif chart['type'] == 'scalar':
      result_values = [chart['value']]

    if not result_values:
      raise ReadValueError('The result value is None.')
    self._Complete(result_values=tuple(result_values))


class ReadHistogramsJsonValue(quest.Quest):

  def __init__(self, hist_name, tir_label=None, story=None, statistic=None):
    self._hist_name = hist_name
    self._tir_label = tir_label
    self._story = story
    self._statistic = statistic

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._hist_name == other._hist_name and
            self._tir_label == other._tir_label and
            self._story == other._story and
            self._statistic == other._statistic)

  def __str__(self):
    return 'Values'

  def Start(self, change, isolate_hash):
    del change
    return _ReadHistogramsJsonValueExecution(self._hist_name, self._tir_label,
                                             self._story, self._statistic,
                                             isolate_hash)

  @classmethod
  def FromDict(cls, arguments):
    chart = arguments.get('chart')
    tir_label = arguments.get('tir_label')
    trace = arguments.get('trace')
    statistic = arguments.get('statistic')
    return cls(chart, tir_label, trace, statistic)


class _ReadHistogramsJsonValueExecution(execution.Execution):

  def __init__(self, hist_name, tir_label, story, statistic, isolate_hash):
    super(_ReadHistogramsJsonValueExecution, self).__init__()
    self._hist_name = hist_name
    self._tir_label = tir_label
    self._story = story
    self._statistic = statistic
    self._isolate_hash = isolate_hash

    self._trace_urls = []

  def _AsDict(self):
    if not self._trace_urls:
      return {}
    return {'traces': self._trace_urls}

  def _Poll(self):
    # TODO(simonhatch): Switch this to use the new perf-output flag instead
    # of the chartjson one. They're functionally equivalent, just new name.
    histogram_dicts = _RetrieveOutputJson(
        self._isolate_hash, 'chartjson-output.json')
    histograms = histogram_set.HistogramSet()
    histograms.ImportDicts(histogram_dicts)
    histograms.ResolveRelatedHistograms()

    matching_histograms = histograms.GetHistogramsNamed(self._hist_name)

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
    self._trace_urls = [
        {'name': t.split('/')[-1], 'url': t} for t in sorted_urls]

    # Filter the histograms by tir_label and story. Getting either the
    # tir_label or the story from a histogram involves pulling out and
    # examining various diagnostics associated with the histogram.
    tir_label = self._tir_label or ''

    matching_histograms = [
        h for h in matching_histograms
        if tir_label == histogram_helpers.GetTIRLabelFromHistogram(h)]


    # If no story is supplied, we're looking for a summary metric so just match
    # on name and tir_label. This is equivalent to the chartjson condition that
    # if no story is specified, look for "summary".
    if self._story:
      matching_histograms = [
          h for h in matching_histograms
          if self._story == _GetStoryFromHistogram(h)]

    # Have to pull out either the raw sample values, or the statistic
    result_values = []
    for h in matching_histograms:
      result_values.extend(self._GetValuesOrStatistic(h))

    if not result_values and self._hist_name:
      name = 'histogram: %s' % self._hist_name
      if tir_label:
        name += ' tir_label: %s' % tir_label
      if self._story:
        name += ' story: %s' % self._story
      raise ReadValueError('Could not find values matching: %s' % name)

    self._Complete(result_values=tuple(result_values))

  def _GetValuesOrStatistic(self, hist):
    if not self._statistic:
      return hist.sample_values

    if not hist.sample_values:
      return []

    # TODO(simonhatch): Use Histogram.getStatisticScalar when it's ported from
    # js.
    if self._statistic == 'avg':
      return [hist.running.mean]
    elif self._statistic == 'min':
      return [hist.running.min]
    elif self._statistic == 'max':
      return [hist.running.max]
    elif self._statistic == 'sum':
      return [hist.running.sum]
    elif self._statistic == 'std':
      return [hist.running.stddev]
    elif self._statistic == 'count':
      return [hist.running.count]
    raise ReadValueError('Unknown statistic type: %s' % self._statistic)


def _ResultValuesFromHistogram(buckets):
  total_count = sum(bucket['count'] for bucket in buckets)

  result_values = []
  for bucket in buckets:
    # TODO: Assumes the bucket is evenly distributed.
    bucket_mean = (bucket['low'] + bucket.get('high', bucket['low'])) / 2
    if total_count > 10000:
      bucket_count = 10000 * bucket['count'] / total_count
    else:
      bucket_count = bucket['count']
    result_values += [bucket_mean] * bucket_count

  return tuple(result_values)


class ReadGraphJsonValue(quest.Quest):

  def __init__(self, chart, trace):
    self._chart = chart
    self._trace = trace

  def __eq__(self, other):
    return (isinstance(other, type(self)) and
            self._chart == other._chart and
            self._trace == other._trace)

  def __str__(self):
    return 'Values'

  def Start(self, change, isolate_hash):
    del change
    return _ReadGraphJsonValueExecution(self._chart, self._trace, isolate_hash)

  @classmethod
  def FromDict(cls, arguments):
    chart = arguments.get('chart')
    trace = arguments.get('trace')
    if not (chart or trace):
      return None
    if chart and not trace:
      raise TypeError('"chart" specified but no "trace" given.')
    if trace and not chart:
      raise TypeError('"trace" specified but no "chart" given.')
    return cls(chart, trace)


class _ReadGraphJsonValueExecution(execution.Execution):

  def __init__(self, chart, trace, isolate_hash):
    super(_ReadGraphJsonValueExecution, self).__init__()
    self._chart = chart
    self._trace = trace
    self._isolate_hash = isolate_hash

  def _AsDict(self):
    return {}

  def _Poll(self):
    graphjson = _RetrieveOutputJson(self._isolate_hash, 'chartjson-output.json')

    if self._chart not in graphjson:
      raise ReadValueError('The chart "%s" is not in the results.' %
                           self._chart)
    if self._trace not in graphjson[self._chart]['traces']:
      raise ReadValueError('The trace "%s" is not in the results.' %
                           self._trace)
    result_value = float(graphjson[self._chart]['traces'][self._trace][0])

    self._Complete(result_values=(result_value,))


def _RetrieveOutputJson(isolate_hash, filename):
  # TODO: Plumb isolate_server through the parameters. crbug.com/822008
  server = 'https://isolateserver.appspot.com'
  output_files = json.loads(isolate.Retrieve(server, isolate_hash))['files']

  if filename not in output_files:
    raise ReadValueError("The test didn't produce %s." % filename)
  output_json_isolate_hash = output_files[filename]['h']
  return json.loads(isolate.Retrieve(server, output_json_isolate_hash))


def _GetStoryFromHistogram(hist):
  stories = hist.diagnostics.get(reserved_infos.STORIES.name)
  if stories and len(stories) == 1:
    return list(stories)[0]
  return None
