# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging
import ntpath
import posixpath

from dashboard.common import histogram_helpers
from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models import evaluators
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models.quest import read_value as read_value_quest
from dashboard.pinpoint.models.tasks import find_isolate
from dashboard.pinpoint.models.tasks import run_test
from tracing.value import histogram_set

HistogramOptions = collections.namedtuple('HistogramOptions',
                                          ('tir_label', 'story', 'statistic'))

GraphJsonOptions = collections.namedtuple('GraphJsonOptions',
                                          ('chart', 'trace'))

TaskOptions = collections.namedtuple(
    'TaskOptions', ('test_options', 'benchmark', 'histogram_options',
                    'graph_json_options', 'mode'))


class CompleteReadValueAction(
    collections.namedtuple('CompleteReadValueAction',
                           ('job', 'task', 'state'))):
  __slots__ = ()

  @task_module.LogStateTransitionFailures
  def __call__(self, _):
    task_module.UpdateTask(
        self.job, self.task.id, new_state=self.state, payload=self.task.payload)


class ReadValueEvaluator(
    collections.namedtuple('ReadValueEvaluator', ('job',))):
  __slots__ = ()

  def CompleteWithError(self, task, reason, message):
    task.payload.update({
        'tries':
            task.payload.get('tries', 0) + 1,
        'errors':
            task.payload.get('errors', []) + [{
                'reason': reason,
                'message': message
            }]
    })
    return [CompleteReadValueAction(self.job, task, 'failed')]

  def __call__(self, task, _, accumulator):
    # TODO(dberris): Validate!
    # Outline:
    #   - Retrieve the data given the options.
    #   - Parse the data from the result file.
    #   - Update the status and payload with an action.

    if task.status in {'completed', 'failed'}:
      return None
    dep = accumulator.get(task.dependencies[0], {})
    isolate_server = dep.get('isolate_server')
    isolate_hash = dep.get('isolate_hash')
    logging.debug('Dependency Data: %s', dep)
    dependency_status = dep.get('status', 'failed')
    if dependency_status == 'failed':
      return self.CompleteWithError(
          task, 'DependencyFailed',
          'Task dependency "%s" ended in failed status.' %
          (task.dependencies[0],))

    if dependency_status in {'pending', 'ongoing'}:
      return None

    try:
      data = read_value_quest.RetrieveOutputJson(
          isolate_server, isolate_hash, task.payload.get('results_filename'))
      if task.payload.get('mode') == 'histogram_sets':
        return self.HandleHistogramSets(task, data)
      elif task.payload.get('mode') == 'graph_json':
        return self.HandleGraphJson(task, data)
      else:
        return self.CompleteWithError(
            task, 'UnsupportedMode',
            ('Pinpoint only currently supports reading '
             'HistogramSets and GraphJSON formatted files.'))
    except (errors.FatalError, errors.InformationalError,
            errors.RecoverableError) as e:
      return self.CompleteWithError(task, type(e).__name__, e.message)

  def HandleHistogramSets(self, task, histogram_dicts):
    histogram_name = task.payload.get('benchmark')
    tir_label = task.payload.get('histogram_options', {}).get('tir_label', '')
    story = task.payload.get('histogram_options', {}).get('story', '')
    statistic = task.payload.get('histogram_options', {}).get('statistic', '')
    histograms = histogram_set.HistogramSet()
    histograms.ImportDicts(histogram_dicts)
    histograms_by_path = read_value_quest.CreateHistogramSetByTestPathDict(
        histograms)
    trace_urls = read_value_quest.FindTraceUrls(histograms)
    test_path_to_match = histogram_helpers.ComputeTestPathFromComponents(
        histogram_name, tir_label=tir_label, story_name=story)
    logging.debug('Test path to match: %s', test_path_to_match)
    result_values = read_value_quest.ExtractValuesFromHistograms(
        test_path_to_match, histograms_by_path, histogram_name, tir_label,
        story, statistic)
    logging.debug('Results: %s', result_values)
    task.payload.update({
        'result_values': result_values,
        'tries': 1,
    })
    if trace_urls:
      task.payload['trace_urls'] = [{
          'key': 'trace',
          'value': url['name'],
          'url': url['url'],
      } for url in trace_urls]
    return [CompleteReadValueAction(self.job, task, 'completed')]

  def HandleGraphJson(self, task, data):
    chart = task.payload.get('graph_json_options', {}).get('chart', '')
    trace = task.payload.get('graph_json_options', {}).get('trace', '')
    if not chart and not trace:
      task.payload.update({
          'result_values': [],
          'tries': task.payload.get('tries', 0) + 1
      })
      return [CompleteReadValueAction(self.job, task, 'completed')]

    if chart not in data:
      raise errors.ReadValueChartNotFound(chart)
    if trace not in data[chart]['traces']:
      raise errors.ReadValueTraceNotFound(trace)
    task.payload.update({
        'result_values': [float(data[chart]['traces'][trace][0])],
        'tries': task.payload.get('tries', 0) + 1
    })
    return [CompleteReadValueAction(self.job, task, 'completed')]


class Evaluator(evaluators.FilteringEvaluator):

  def __init__(self, job):
    super(Evaluator, self).__init__(
        predicate=evaluators.All(
            evaluators.TaskTypeEq('read_value'),
            evaluators.TaskStatusIn({'pending'})),
        delegate=evaluators.SequenceEvaluator(
            evaluators=(evaluators.TaskPayloadLiftingEvaluator(),
                        ReadValueEvaluator(job))))


def CreateGraph(options):
  if not isinstance(options, TaskOptions):
    raise ValueError('options must be an instance of read_value.TaskOptions')
  subgraph = run_test.CreateGraph(options.test_options)
  path = None
  if read_value_quest.IsWindows({'dimensions': options.test_options.dimensions
                                }):
    path = ntpath.join(options.benchmark, 'perf_results.json')
  else:
    path = posixpath.join(options.benchmark, 'perf_results.json')

  # We create a 1:1 mapping between a read_value task and a run_test task.
  def GenerateVertexAndDep(attempts):
    for attempt in range(attempts):
      change_id = find_isolate.ChangeId(
          options.test_options.build_options.change)
      read_value_id = 'read_value_%s_%s' % (change_id, attempt)
      run_test_id = run_test.TaskId(change_id, attempt)
      yield (task_module.TaskVertex(
          id=read_value_id,
          vertex_type='read_value',
          payload={
              'benchmark': options.benchmark,
              'mode': options.mode,
              'results_filename': path,
              'histogram_options': {
                  'tir_label': options.histogram_options.tir_label,
                  'story': options.histogram_options.story,
                  'statistic': options.histogram_options.statistic,
              },
              'graph_json_options': {
                  'chart': options.graph_json_options.chart,
                  'trace': options.graph_json_options.trace
              },
              'change': options.test_options.build_options.change.AsDict(),
          }), task_module.Dependency(from_=read_value_id, to=run_test_id))

  for vertex, edge in GenerateVertexAndDep(options.test_options.attempts):
    subgraph.vertices.append(vertex)
    subgraph.edges.append(edge)

  return subgraph
