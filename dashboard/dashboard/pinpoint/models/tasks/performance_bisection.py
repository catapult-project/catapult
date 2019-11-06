# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import itertools
import logging
import math

from dashboard.common import math_utils
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import compare
from dashboard.pinpoint.models import evaluators
from dashboard.pinpoint.models import exploration
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models.tasks import find_isolate
from dashboard.pinpoint.models.tasks import read_value
from dashboard.pinpoint.models.tasks import run_test
from dashboard.services import gitiles_service

_DEFAULT_SPECULATION_LEVELS = 2

AnalysisOptions = collections.namedtuple('AnalysisOptions', (
    'comparison_magnitude',
    'min_attempts',
    'max_attempts',
))

BuildOptionTemplate = collections.namedtuple('BuildOptionTemplate',
                                             ('builder', 'target', 'bucket'))

TestOptionTemplate = collections.namedtuple(
    'TestOptionTemplate', ('swarming_server', 'dimensions', 'extra_args'))

ReadOptionTemplate = collections.namedtuple(
    'ReadOptionTemplate',
    ('benchmark', 'histogram_options', 'graph_json_options', 'mode'))

TaskOptions = collections.namedtuple(
    'TaskOptions',
    ('build_option_template', 'test_option_template', 'read_option_template',
     'analysis_options', 'start_change', 'end_change', 'pinned_change'))


def _CreateReadTaskOptions(build_option_template, test_option_template,
                           read_option_template, analysis_options, change):
  return read_value.TaskOptions(
      test_options=run_test.TaskOptions(
          build_options=find_isolate.TaskOptions(
              change=change, **build_option_template._asdict()),
          attempts=analysis_options.min_attempts,
          **test_option_template._asdict()),
      **read_option_template._asdict())


def CreateGraph(options):
  if not isinstance(options, TaskOptions):
    raise ValueError(
        'options must be an instance of performance_bisection.TaskOptions')

  start_change = options.start_change
  end_change = options.end_change
  if options.pinned_change:
    start_change.Update(options.pinned_change)
    end_change.Update(options.pinned_change)

  start_change_read_options = _CreateReadTaskOptions(
      options.build_option_template, options.test_option_template,
      options.read_option_template, options.analysis_options, start_change)
  end_change_read_options = _CreateReadTaskOptions(
      options.build_option_template, options.test_option_template,
      options.read_option_template, options.analysis_options, end_change)

  # Given the start_change and end_change, we create two subgraphs that we
  # depend on from the 'find_culprit' task. This means we'll need to create
  # independent test options and build options from the template provided by the
  # caller.
  start_subgraph = read_value.CreateGraph(start_change_read_options)
  end_subgraph = read_value.CreateGraph(end_change_read_options)

  # Then we add a dependency from the 'FindCulprit' task with the payload
  # describing the options set for the performance bisection.
  find_culprit_task = task_module.TaskVertex(
      id='performance_bisection',
      vertex_type='find_culprit',
      payload={
          'start_change':
              options.start_change.AsDict(),
          'end_change':
              options.end_change.AsDict(),
          'pinned_change':
              options.pinned_change.AsDict() if options.pinned_change else None,
          # We still persist the templates, because we'll need that data in case
          # we are going to extend the graph with the same build/test templates
          # in subgraphs.
          'analysis_options':
              options.analysis_options._asdict(),
          'build_option_template':
              options.build_option_template._asdict(),
          'test_option_template':
              options.test_option_template._asdict(),
          'read_option_template': {
              'histogram_options':
                  options.read_option_template.histogram_options._asdict(),
              'graph_json_options':
                  options.read_option_template.graph_json_options._asdict(),
              'benchmark':
                  options.read_option_template.benchmark,
              'mode':
                  options.read_option_template.mode,
          },
      })
  return task_module.TaskGraph(
      vertices=list(
          itertools.chain(start_subgraph.vertices, end_subgraph.vertices)) +
      [find_culprit_task],
      edges=list(itertools.chain(start_subgraph.edges, end_subgraph.edges)) + [
          task_module.Dependency(from_=find_culprit_task.id, to=v.id)
          for v in itertools.chain(start_subgraph.vertices,
                                   end_subgraph.vertices)
          if v.vertex_type == 'read_value'
      ])


class PrepareCommits(collections.namedtuple('PrepareCommits', ('job', 'task'))):
  # Save memory and avoid unnecessarily adding more attributes to objects of
  # this type.
  __slots__ = ()

  @task_module.LogStateTransitionFailures
  def __call__(self, _):
    start_change = change_module.Change.FromDict(
        self.task.payload['start_change'])
    end_change = change_module.Change.FromDict(self.task.payload['end_change'])
    try:
      # We're storing this once, so that we don't need to always get this when
      # working with the individual commits. This reduces our reliance on
      # datastore operations throughout the course of handling the culprit
      # finding process.
      #
      # TODO(dberris): Expand the commits into the full table of dependencies?
      # Because every commit in the chromium repository is likely to be building
      # against different versions of the dependencies (v8, skia, etc.)
      # we'd need to expand the concept of a changelist (CL, or Change in the
      # Pinpoint codebase) so that we know which versions of the dependencies to
      # use in specific CLs. Once we have this, we might be able to operate
      # cleanly on just Change instances instead of just raw commits.
      #
      # TODO(dberris): Model the "merge-commit" like nature of auto-roll CLs by
      # allowing the preparation action to model the non-linearity of the
      # history. This means we'll need a concept of levels, where changes in a
      # single repository history (the main one) operates at a higher level
      # linearly, and if we're descending into rolls that we're exploring a
      # lower level in the linear history. This is similar to the following
      # diagram:
      #
      #   main -> m0 -> m1 -> m2 -> roll0 -> m3 -> ...
      #                              |
      #   dependency ..............  +-> d0 -> d1
      #
      # Ideally we'll already have this expanded before we go ahead and perform
      # a bisection, to amortise the cost of making requests to back-end
      # services for this kind of information in tight loops.
      commits = change_module.Commit.CommitRange(start_change.base_commit,
                                                 end_change.base_commit)
      self.task.payload.update({
          'commits': [
              collections.OrderedDict(
                  [('repository', start_change.base_commit.repository),
                   ('git_hash', start_change.base_commit.git_hash)])
          ] + [
              collections.OrderedDict(
                  [('repository', start_change.base_commit.repository),
                   ('git_hash', commit['commit'])])
              for commit in reversed(commits)
          ]
      })
      task_module.UpdateTask(
          self.job,
          self.task.id,
          new_state='ongoing',
          payload=self.task.payload)
    except gitiles_service.NotFoundError as e:
      # TODO(dberris): We need to be more resilient to intermittent failures
      # from the Gitiles service here.
      self.task.payload.update({
          'errors':
              self.task.payload.get('errors', []) + [{
                  'reason': 'GitilesFetchError',
                  'message': e.message
              }]
      })
      task_module.UpdateTask(
          self.job, self.task.id, new_state='failed', payload=self.task.payload)

  def __str__(self):
    return 'PrepareCLs( job = %s, task = %s )' % (self.job.job_id, self.task.id)


class RefineExplorationAction(
    collections.namedtuple('RefineExplorationAction',
                           ('job', 'task', 'change', 'additional_attempts'))):
  __slots__ = ()

  def __str__(self):
    return ('RefineExplorationAction(job = %s, task = %s, change = %s, +%s '
            'attempts)') % (self.job.job_id, self.task.id,
                            self.change.id_string, self.additional_attempts)

  def __call__(self, accumulator):
    # Outline:
    #   - Given the job and task, extend the TaskGraph to add new tasks and
    #     dependencies, being careful to filter the IDs from what we already see
    #     in the accumulator to avoid graph amendment errors.
    #   - If we do encounter graph amendment errors, we should log those and not
    #     block progress because that can only happen if there's concurrent
    #     updates being performed with the same actions.
    build_option_template = BuildOptionTemplate(
        **self.task.payload.get('build_option_template'))
    test_option_template = TestOptionTemplate(
        **self.task.payload.get('test_option_template'))

    # The ReadOptionTemplate is special because it has nested structures, so
    # we'll have to reconstitute those accordingly.
    read_option_template_map = self.task.payload.get('read_option_template')
    read_option_template = ReadOptionTemplate(
        benchmark=self.task.payload.get('read_option_template').get(
            'benchmark'),
        histogram_options=read_value.HistogramOptions(
            **read_option_template_map.get('histogram_options')),
        graph_json_options=read_value.GraphJsonOptions(
            **read_option_template_map.get('graph_json_options')),
        mode=read_option_template_map.get('mode'))

    analysis_options_dict = self.task.payload.get('analysis_options')
    if self.additional_attempts:
      analysis_options_dict['min_attempts'] = min(
          analysis_options_dict.get('min_attempts', 0) +
          self.additional_attempts,
          analysis_options_dict.get('max_attempts', 100))
    analysis_options = AnalysisOptions(**analysis_options_dict)

    new_subgraph = read_value.CreateGraph(
        _CreateReadTaskOptions(build_option_template, test_option_template,
                               read_option_template, analysis_options,
                               self.change))
    try:
      task_module.ExtendTaskGraph(
          self.job,
          vertices=[
              # Add all of the new vertices we do not have in the graph yet.
              v for v in new_subgraph.vertices if v.id not in accumulator
          ],
          dependencies=[
              # Only add dependencies to the new 'read_value' tasks.
              task_module.Dependency(from_=self.task.id, to=v.id)
              for v in new_subgraph.vertices
              if v.id not in accumulator and v.vertex_type == 'read_value'
          ])
    except task_module.InvalidAmendment as e:
      logging.error('Failed to amend graph: %s', e)


class CompleteExplorationAction(
    collections.namedtuple('CompleteExplorationAction',
                           ('job', 'task', 'state'))):
  __slots__ = ()

  def __str__(self):
    return 'CompleteExplorationAction(job = %s, task = %s, state = %s)' % (
        self.job.job_id, self.task.id, self.state)

  @task_module.LogStateTransitionFailures
  def __call__(self, accumulator):
    # TODO(dberris): Maybe consider cancelling outstanding actions? Here we'll
    # need a way of synthesising actions if we want to force the continuation of
    # a task graph's evaluation.
    task_module.UpdateTask(
        self.job, self.task.id, new_state=self.state, payload=self.task.payload)


class FindCulprit(collections.namedtuple('FindCulprit', ('job'))):
  __slots__ = ()

  def __call__(self, task, event, accumulator):
    # Outline:
    #  - If the task is still pending, this means this is the first time we're
    #  encountering the task in an evaluation. Set up the payload data to
    #  include the full range of commits, so that we load it once and have it
    #  ready, and emit an action to mark the task ongoing.
    #
    #  - If the task is ongoing, gather all the dependency data (both results
    #  and status) and see whether we have enough data to determine the next
    #  action. We have three main cases:
    #
    #    1. We cannot detect a significant difference between the results from
    #       two different CLs. We call this the NoReproduction case.
    #
    #    2. We do not have enough confidence that there's a difference. We call
    #       this the Indeterminate case.
    #
    #    3. We have enough confidence that there's a difference between any two
    #       ordered changes. We call this the SignificantChange case.
    #
    # - Delegate the implementation to handle the independent cases for each
    #   change point we find in the CL continuum.
    if task.status == 'pending':
      return [PrepareCommits(self.job, task)]

    if task.status == 'ongoing':
      # TODO(dberris): Validate and fail gracefully instead of asserting?
      assert 'commits' in task.payload, ('Programming error, need commits to '
                                         'proceed!')

      # Collect all the dependency task data and analyse the results.
      # Group them by change.
      # Order them by appearance in the CL range.
      # Also count the status per CL (failed, ongoing, etc.)
      deps = set(task.dependencies)
      results_by_change = collections.defaultdict(list)
      status_by_change = collections.defaultdict(dict)
      changes_with_data = set()
      changes_by_status = collections.defaultdict(set)

      # TODO(dberris): Determine a better way of creating these Change objects
      # which doesn't involve these .FromDict(...) calls which might force calls
      # to back-end services.
      associated_results = [(change_module.Change.FromDict(t.get('change')),
                             t.get('status'), t.get('result_values'))
                            for dep, t in accumulator.items()
                            if dep in deps]
      for change, status, result_values in associated_results:
        if result_values:
          filtered_results = [r for r in result_values if r is not None]
          if filtered_results:
            results_by_change[change].append(filtered_results)
        status_by_change[change].update({
            status: status_by_change[change].get(status, 0) + 1,
        })
        changes_by_status[status].add(change)
        if status not in {'ongoing', 'pending'}:
          changes_with_data.add(change)

      # If the dependencies have converged into a single status, we can make
      # decisions on the terminal state of the bisection.
      if len(changes_by_status) == 1 and changes_with_data:

        # Check whether all dependencies are completed and if we do
        # not have data in any of the dependencies.
        if changes_by_status['completed'] == changes_with_data:
          changes_with_empty_results = [
              change for change in changes_with_data
              if not results_by_change[change]
          ]
          if changes_with_empty_results:
            task.payload.update({
                'errors':
                    task.payload.get('errors', []) + [{
                        'reason':
                            'BisectionFailed',
                        'message': ('We did not find any results from '
                                    'successful test runs.')
                    }]
            })
            return [CompleteExplorationAction(self.job, task, 'failed')]

        # Check whether all the dependencies had the tests fail consistently.
        if changes_by_status['failed'] == changes_with_data:
          task.payload.update({
              'errors':
                  task.payload.get('errors', []) + [{
                      'reason': 'BisectionFailed',
                      'message': 'All attempts in all dependencies failed.'
                  }]
          })
          return [CompleteExplorationAction(self.job, task, 'failed')]

      # We want to reduce the list of ordered changes to only the ones that have
      # data available.
      all_changes = [
          change_module.Change(
              commits=[
                  change_module.Commit(
                      repository=commit.get('repository'),
                      git_hash=commit.get('git_hash'))
              ],
              patch=task.payload.get('pinned_change'))
          for commit in task.payload.get('commits', [])
      ]
      change_index = {change: index for index, change in enumerate(all_changes)}
      ordered_changes = [c for c in all_changes if c in changes_with_data]

      if len(ordered_changes) < 2:
        # We do not have enough data yet to determine whether we should do
        # anything.
        return None

      # From here we can then do the analysis on a pairwise basis, as we're
      # going through the list of Change instances we have data for.
      # NOTE: A lot of this algorithm is already in pinpoint/models/job_state.py
      # which we're adapting.
      def Compare(a, b):
        # This is the comparison function which determines whether the samples
        # we have from the two changes (a and b) are statistically significant.
        if 'pending' in status_by_change[a] or 'pending' in status_by_change[b]:
          return compare.PENDING

        # NOTE: Here we're attempting to scale the provided comparison magnitude
        # threshold by using the central tendencies (means) of the resulting
        # values from individual test attempt results, and scaling those by the
        # larger inter-quartile range (a measure of dispersion, simply computed
        # as the 75th percentile minus the 25th percentile). The reason we're
        # doing this is so that we can scale the tolerance according to the
        # noise inherent in the measurements -- i.e. more noisy measurements
        # will require a larger difference for us to consider statistically
        # significant.
        #
        # NOTE: We've changed this computation to consider the consolidated
        # measurements for a single change, instead of looking at the means,
        # since we cannot assume that the means can be relied on as a good
        # measure of central tendency for small sample sizes.
        values_for_a = tuple(itertools.chain(*results_by_change[a]))
        values_for_b = tuple(itertools.chain(*results_by_change[b]))
        max_iqr = max(
            math_utils.Iqr(values_for_a), math_utils.Iqr(values_for_b), 0.001)
        comparison_magnitude = task.payload.get('comparison_magnitude',
                                                1.0) / max_iqr
        attempts = (len(values_for_a) + len(values_for_b)) // 2
        return compare.Compare(values_for_a, values_for_b, attempts,
                               'performance', comparison_magnitude)

      def DetectChange(change_a, change_b):
        # We return None if the comparison determines that the result is
        # inconclusive. This is required by the exploration.Speculate contract.
        comparison = Compare(change_a, change_b)
        if comparison == compare.UNKNOWN:
          return None
        return comparison == compare.DIFFERENT

      changes_to_refine = []

      def CollectChangesToRefine(a, b):
        # Here we're collecting changes that need refinement, which happens when
        # two changes when compared yield the "unknown" result.
        attempts_for_a = sum(status_by_change[a].values())
        attempts_for_b = sum(status_by_change[b].values())
        if min(attempts_for_a, attempts_for_b) == task.payload.get(
            'analysis_options').get('max_attempts'):
          return None

        # Grow the attempts by 50% every time when increasing attempt counts.
        # This number is arbitrary, and we should probably use something like a
        # Fibonacci sequence when scaling attempt counts.
        additional_attempts = int(
            math.floor(min(attempts_for_a, attempts_for_b) * 0.5))
        changes_to_refine.append(
            (a if attempts_for_a <= attempts_for_b else b, additional_attempts))
        return None

      def FindMidpoint(a, b):
        # Here we use the (very simple) midpoint finding algorithm given that we
        # already have the full range of commits to bisect through.
        a_index = change_index[a]
        b_index = change_index[b]
        subrange = all_changes[a_index:b_index + 1]
        return None if len(subrange) <= 2 else subrange[len(subrange) // 2]

      additional_changes = exploration.Speculate(
          ordered_changes,
          change_detected=DetectChange,
          on_unknown=CollectChangesToRefine,
          midpoint=FindMidpoint,
          levels=_DEFAULT_SPECULATION_LEVELS)

      # At this point we can collect the actions to extend the task graph based
      # on the results of the speculation.
      actions = [
          RefineExplorationAction(self.job, task, change, more_attempts)
          for change, more_attempts in itertools.chain(
              [(c, 0) for _, c in additional_changes],
              [(c, a) for c, a in changes_to_refine],
          )
      ]

      # Here we collect the points where we've found the changes.
      def Pairwise(iterable):
        """s -> (s0, s1), (s1, s2), (s2, s3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return itertools.izip(a, b)

      task.payload.update({
          'culprits': [(a.AsDict(), b.AsDict())
                       for a, b in Pairwise(ordered_changes)
                       if DetectChange(a, b)]
      })
      if not actions:
        # Mark this operation complete, storing the differences we can compute.
        actions = [CompleteExplorationAction(self.job, task, 'completed')]
      return actions


class Evaluator(evaluators.FilteringEvaluator):

  def __init__(self, job):
    super(Evaluator, self).__init__(
        predicate=evaluators.All(
            evaluators.TaskTypeEq('find_culprit'),
            evaluators.Not(evaluators.TaskStatusIn({'completed', 'failed'}))),
        delegate=FindCulprit(job))
