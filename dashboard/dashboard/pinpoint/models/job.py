# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import logging
import os
import sys
import traceback
import uuid

from google.appengine.api import datastore_errors
from google.appengine.api import taskqueue
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.runtime import apiproxy_errors

from dashboard.common import utils
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models import evaluators
from dashboard.pinpoint.models import event as event_module
from dashboard.pinpoint.models import job_bug_update
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint.models import results2
from dashboard.pinpoint.models import scheduler
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models import timing_record
from dashboard.pinpoint.models.evaluators import job_serializer
from dashboard.pinpoint.models.tasks import evaluator as task_evaluator
from dashboard.services import gerrit_service
from dashboard.services import issue_tracker_service

# We want this to be fast to minimize overhead while waiting for tasks to
# finish, but don't want to consume too many resources.
_TASK_INTERVAL = 60

_CRYING_CAT_FACE = u'\U0001f63f'
_INFINITY = u'\u221e'
_RIGHT_ARROW = u'\u2192'
_ROUND_PUSHPIN = u'\U0001f4cd'

_MAX_RECOVERABLE_RETRIES = 3

OPTION_STATE = 'STATE'
OPTION_TAGS = 'TAGS'
OPTION_ESTIMATE = 'ESTIMATE'
OPTION_INPUTS = 'INPUTS'

COMPARISON_MODES = job_state.COMPARISON_MODES

RETRY_OPTIONS = taskqueue.TaskRetryOptions(
    task_retry_limit=8, min_backoff_seconds=2)

_FIRST_OR_LAST_FAILED_COMMENT = (
    u"""One or both of the initial changes failed to produce any results.
Perhaps the job is misconfigured or the tests are broken? See the job
page for details.""")


def JobFromId(job_id):
  """Get a Job object from its ID.

  Its ID is just its key as a hex string.

  Users of Job should not have to import ndb. This function maintains an
  abstraction layer that separates users from the Datastore details.
  """
  job_key = ndb.Key('Job', int(job_id, 16))
  return job_key.get()


def IsDone(job_id):
  """Transactionally check whether a job is done executing.

  Returns True IFF the job is executing under the execution engine and that
  internal state is consistent with the job being "done".

  Raises any errors encountered in execution engine evaluation.
  """
  job = JobFromId(job_id)
  if not job.use_execution_engine:
    return False

  # This comes from an eventually consistent read, but we can treat that as a
  # relaxed load -- if this ever is true, then that means a transaction before
  # this call had already marked the job "done".
  if job.done:
    return True

  try:
    context = task_module.Evaluate(
        job, event_module.SelectEvent(),
        evaluators.DispatchByTaskType({
            'find_culprit':
                evaluators.TaskPayloadLiftingEvaluator(exclude_keys=['commits'])
        }))
    if not context:
      return False
    for payload in context.values():
      status = payload.get('status')
      if status in {'pending', 'ongoing'}:
        return False
    return True
  except task_module.Error as error:
    logging.error('Evaluation error: %s', error)
    raise


@ndb.transactional
def MarkDone(job_id):
  """Transactionally update the job as done.

  This only works for jobs executing under the execution engine.

  Returns True on a successful update.
  """
  job = JobFromId(job_id)
  if job.done:
    return False
  job.done = True
  job.put()
  return True


@ndb.transactional
def UpdateTime(job_id):
  """Transactionally updates the updated propery of a job."""
  job = JobFromId(job_id)
  job.updated = datetime.datetime.utcnow()
  job.put()


class BenchmarkArguments(ndb.Model):
  """Structured version of the ad-hoc 'arguments' JSON for a Job.

  This class formalises the structure of the arguments passed into, and
  supported by the Job model. This is intended to be used as a structured
  property of Job, not a standalone entity.
  """
  benchmark = ndb.StringProperty(indexed=True)
  story = ndb.StringProperty(indexed=True)
  story_tags = ndb.StringProperty(indexed=True)
  chart = ndb.StringProperty(indexed=True)
  statistic = ndb.StringProperty(indexed=True)

  @classmethod
  def FromArgs(cls, args):
    return cls(
        benchmark=args.get('benchmark'),
        story=args.get('story'),
        story_tags=args.get('story_tags'),
        chart=args.get('chart'),
        statistic=args.get('statistic'),
    )


def IsRunning(job):
  if not job.use_execution_engine:
    return job.started and not job.cancelled and job.task and len(job.task) > 0
  return job.started and not job.completed


class Job(ndb.Model):
  """A Pinpoint job."""

  state = ndb.PickleProperty(required=True, compressed=True)

  #####
  # Job arguments passed in through the API.
  #####

  # Request parameters.
  arguments = ndb.JsonProperty(required=True)
  bug_id = ndb.IntegerProperty()
  project = ndb.StringProperty(default='chromium')
  comparison_mode = ndb.StringProperty()

  # The Gerrit server url and change id of the code review to update upon
  # completion.
  gerrit_server = ndb.StringProperty()
  gerrit_change_id = ndb.StringProperty()

  # User-provided name of the job.
  name = ndb.StringProperty()
  tags = ndb.JsonProperty()

  # Email of the job creator.
  user = ndb.StringProperty()

  created = ndb.DateTimeProperty(required=True, auto_now_add=True)

  # This differs from "created" since there may be a lag between the time it
  # was queued and when the scheduler actually starts the job.
  started_time = ndb.DateTimeProperty(required=False)

  # Don't use `auto_now` for `updated`. When we do data migration, we need
  # to be able to modify the Job without changing the Job's completion time.
  updated = ndb.DateTimeProperty(required=True, auto_now_add=True)
  started = ndb.BooleanProperty(default=True)
  completed = ndb.ComputedProperty(lambda self: self.done or (
      not self.use_execution_engine and self.started and not self.task))
  failed = ndb.ComputedProperty(lambda self: bool(self.exception_details_dict))
  running = ndb.ComputedProperty(IsRunning)
  cancelled = ndb.BooleanProperty(default=False)
  cancel_reason = ndb.TextProperty()

  # Because of legacy reasons, `completed` is not exactly representative of
  # whether a job is "done" from the execution engine's point of view. We're
  # introducing this top-level property as a definitive flag, transactionally
  # enforced, to signal whether we are done executing a job.
  done = ndb.BooleanProperty(default=False)

  # The name of the Task Queue task this job is running on. If it's present, the
  # job is running. The task is also None for Task Queue retries.
  task = ndb.StringProperty()

  # The contents of any Exception that was thrown to the top level.
  # If it's present, the job failed.
  exception = ndb.TextProperty()
  exception_details = ndb.JsonProperty()
  difference_count = ndb.IntegerProperty()
  retry_count = ndb.IntegerProperty(default=0)

  # We expose the configuration as a first-class property of the Job.
  configuration = ndb.ComputedProperty(
      lambda self: self.arguments.get('configuration'))

  # Pull out the benchmark, chart, and statistic as a structured property at the
  # top-level, so that we can analyse these in a structured manner.
  benchmark_arguments = ndb.StructuredProperty(BenchmarkArguments)

  # Indicate whether we should evaluate this job's tasks through the execution
  # engine.
  use_execution_engine = ndb.BooleanProperty(default=False, indexed=False)

  # Priority for scheduling purposes. Lower numbers indicate higher priority.
  priority = ndb.IntegerProperty(default=0)

  # Jobs can be part of batches, which have an id provided by the creator.
  batch_id = ndb.StringProperty()

  @classmethod
  def _post_get_hook(cls, key, future):  # pylint: disable=unused-argument
    e = future.get_result()
    if not e:
      return

    if not getattr(e, 'exception_details'):
      e.exception_details = e.exception_details_dict

  @property
  def exception_details_dict(self):
    if hasattr(self, 'exception_details'):
      if self.exception_details:
        return self.exception_details

    if hasattr(self, 'exception'):
      exc = self.exception
      if exc:
        return {'message': exc.splitlines()[-1], 'traceback': exc}

    return None

  @classmethod
  def New(cls,
          quests,
          changes,
          arguments=None,
          bug_id=None,
          comparison_mode=None,
          comparison_magnitude=None,
          gerrit_server=None,
          gerrit_change_id=None,
          name=None,
          pin=None,
          tags=None,
          user=None,
          priority=None,
          use_execution_engine=False,
          project='chromium',
          batch_id=None):
    """Creates a new Job, adds Changes to it, and puts it in the Datstore.

    Args:
      quests: An iterable of Quests for the Job to run.
      changes: An iterable of the initial Changes to run on.
      arguments: A dict with the original arguments used to start the Job.
      bug_id: A monorail issue id number to post Job updates to.
      comparison_mode: Either 'functional' or 'performance', which the Job uses
        to figure out whether to perform a functional or performance bisect. If
        None, the Job will not automatically add any Attempts or Changes.
      comparison_magnitude: The estimated size of the regression or improvement
        to look for. Smaller magnitudes require more repeats.
      gerrit_server: Server of the Gerrit code review to update with job
        results.
      gerrit_change_id: Change id of the Gerrit code review to update with job
        results.
      name: The user-provided name of the Job.
      pin: A Change (Commits + Patch) to apply to every Change in this Job.
      tags: A dict of key-value pairs used to filter the Jobs listings.
      user: The email of the Job creator.
      priority: An integer indicating priority.
      use_execution_engine: A bool indicating whether to use the experimental
        execution engine. Currently defaulted to False, but will be switched to
        True and eventually removed as an option later.
      project: A Monorail project ID.
      batch_id: An ID provided to link multiple jobs together.

    Returns:
      A Job object.
    """
    state = job_state.JobState(
        quests,
        comparison_mode=comparison_mode,
        comparison_magnitude=comparison_magnitude,
        pin=pin)
    args = arguments or {}
    job = cls(
        state=state,
        arguments=args,
        bug_id=bug_id,
        comparison_mode=comparison_mode,
        gerrit_server=gerrit_server,
        gerrit_change_id=gerrit_change_id,
        name=name,
        tags=tags,
        user=user,
        started=False,
        cancelled=False,
        use_execution_engine=use_execution_engine,
        priority=priority,
        project=project,
        batch_id=batch_id,
    )

    # Pull out the benchmark arguments to the top-level.
    job.benchmark_arguments = BenchmarkArguments.FromArgs(args)

    if use_execution_engine:
      # Short-circuit the process because we don't need any further processing
      # here when we're using the execution engine.
      job.put()
      return job

    for c in changes:
      job.AddChange(c)

    job.put()

    # At this point we already have an ID, so we should go through each of the
    # quests associated with the state, and provide the Job ID through a common
    # API.
    job.state.PropagateJob(job)
    job.put()
    return job

  def PostCreationUpdate(self):
    pending = 0
    if self.configuration:
      try:
        pending = scheduler.QueueStats(self.configuration).get('queued_jobs', 0)
      except (scheduler.QueueNotFound, ndb.BadRequestError) as e:
        logging.warning('Error encountered fetching queue named "%s": %s ',
                        self.configuration, e)

    bug_update = job_bug_update.JobUpdateBuilder(self).CreationUpdate(pending)
    deferred.defer(
        _PostBugCommentDeferred,
        self.bug_id,
        bug_update.comment_text,
        project=self.project,
        send_email=True,
        _retry_options=RETRY_OPTIONS)

  @property
  def job_id(self):
    return '%x' % self.key.id()

  @property
  def status(self):
    if self.failed:
      return 'Failed'

    if self.cancelled:
      return 'Cancelled'

    if self.completed:
      return 'Completed'

    if self.running:
      return 'Running'

    # By default, we assume that the Job is queued.
    return 'Queued'

  @property
  def url(self):
    host = os.environ['HTTP_HOST']
    # TODO(crbug.com/939723): Remove this workaround when not needed.
    if host == 'pinpoint.chromeperf.appspot.com':
      host = 'pinpoint-dot-chromeperf.appspot.com'
    return 'https://%s/job/%s' % (host, self.job_id)

  @property
  def results_url(self):
    if not self.task:
      url = results2.GetCachedResults2(self)
      if url:
        return url
    # Point to the default status page if no results are available.
    return '/results2/%s' % self.job_id

  @property
  def auto_name(self):
    if self.name:
      return self.name

    if self.comparison_mode == job_state.FUNCTIONAL:
      name = 'Functional bisect'
    elif self.comparison_mode == job_state.PERFORMANCE:
      name = 'Performance bisect'
    else:
      name = 'Try job'

    if self.configuration:
      name += ' on ' + self.configuration
      if 'benchmark' in self.arguments:
        name += '/' + self.arguments['benchmark']

    return name

  def AddChange(self, change):
    self.state.AddChange(change)

  def Start(self):
    """Starts the Job and updates it in the Datastore.

    This method is designed to return fast, so that Job creation is responsive
    to the user. It schedules the Job on the task queue without running
    anything. It also posts a bug comment, and updates the Datastore.
    """
    if self.use_execution_engine:
      # Treat this as if it's a poll, and run the handler here.
      try:
        task_module.Evaluate(
            self,
            event_module.Event(type='initiate', target_task=None, payload={}),
            task_evaluator.ExecutionEngine(self)),
      except task_module.Error as error:
        logging.error('Failed: %s', error)
        self.Fail()
        self.put()
        return
    else:
      self._Schedule()
    self.started = True
    self.started_time = datetime.datetime.now()
    self.put()

    title = _ROUND_PUSHPIN + ' Pinpoint job started.'
    comment = '\n'.join((title, self.url))
    deferred.defer(
        _PostBugCommentDeferred,
        self.bug_id,
        comment,
        labels=job_bug_update.ComputeLabelUpdates(['Pinpoint-Job-Started']),
        project=self.project,
        send_email=True,
        _retry_options=RETRY_OPTIONS)

  def _IsTryJob(self):
    return not self.comparison_mode or self.comparison_mode == job_state.TRY

  def _Complete(self):
    logging.debug('Job [%s]: Completed', self.job_id)
    if self.use_execution_engine:
      scheduler.Complete(self)

      # Only proceed if this thread/process is the one that successfully marked
      # a job done.
      if not MarkDone(self.job_id):
        return
      logging.debug('Job [%s]: Marked done', self.job_id)

    if not self._IsTryJob() and not self.use_execution_engine:
      self.difference_count = len(self.state.Differences())

    try:
      # TODO(dberris): Migrate results2 generation to tasks and evaluators.
      results2.ScheduleResults2Generation(self)
    except taskqueue.Error as e:
      logging.debug('Failed ScheduleResults2Generation: %s', str(e))

    self._FormatAndPostBugCommentOnComplete()
    self._UpdateGerritIfNeeded()
    scheduler.Complete(self)

  def _FormatAndPostBugCommentOnComplete(self):
    logging.debug('Processing outputs.')
    if self._IsTryJob():
      # There is no comparison metric.
      title = '<b>%s Job complete. See results below.</b>' % _ROUND_PUSHPIN
      deferred.defer(
          _PostBugCommentDeferred,
          self.bug_id,
          '\n'.join((title, self.url)),
          project=self.project,
          labels=['Pinpoint-Tryjob-Completed'],
          _retry_options=RETRY_OPTIONS)
      return

    # There is a comparison metric.
    differences = []
    result_values = {}
    changes_examined = None
    if not self.use_execution_engine:
      differences = self.state.Differences()
      for change_a, change_b in differences:
        result_values.setdefault(change_a, self.state.ResultValues(change_a))
        result_values.setdefault(change_b, self.state.ResultValues(change_b))
      changes_examined = self.state.ChangesExamined()
    else:
      logging.debug('Execution Engine: Finding culprits.')
      context = task_module.Evaluate(
          self, event_module.SelectEvent(),
          evaluators.Selector(
              event_type='select',
              include_keys={'culprits', 'change', 'result_values'}))
      differences = [(change_module.ReconstituteChange(change_a),
                      change_module.ReconstituteChange(change_b))
                     for change_a, change_b in context.get(
                         'performance_bisection', {}).get('culprits', [])]
      result_values = {
          change_module.ReconstituteChange(v.get('change')):
          v.get('result_values')
          for v in context.values()
          if 'change' in v and 'result_values' in v
      }

    if not differences:
      # First, check if there are no differences because one side of bisection
      # failed outright.
      if self.state.FirstOrLastChangeFailed():
        title = "<b>%s Job finished with errors.</b>" % _CRYING_CAT_FACE
        comment = '\n'.join(
            (title, self.url, '', _FIRST_OR_LAST_FAILED_COMMENT))
        deferred.defer(
            _PostBugCommentDeferred,
            self.bug_id,
            comment,
            project=self.project,
            labels=job_bug_update.ComputeLabelUpdates(['Pinpoint-Job-Failed']),
            _retry_options=RETRY_OPTIONS)
        return

      # When we cannot find a difference, we want to not only update the issue
      # with that (minimal) information but also automatically mark the issue
      # WontFix. This is based on information we've gathered in production that
      # most issues where we find Pinpoint cannot reproduce the difference end
      # up invariably as "Unconfirmed" with very little follow-up.
      title = "<b>%s Couldn't reproduce a difference.</b>" % _ROUND_PUSHPIN
      deferred.defer(
          _PostBugCommentDeferred,
          self.bug_id,
          '\n'.join((title, self.url)),
          project=self.project,
          labels=job_bug_update.ComputeLabelUpdates(
              ['Pinpoint-Job-Completed', 'Pinpoint-No-Repro']),
          status='WontFix',
          _retry_options=RETRY_OPTIONS)
      return

    # Collect the result values for each of the differences
    bug_update_builder = job_bug_update.DifferencesFoundBugUpdateBuilder(
        self.state.metric)
    bug_update_builder.SetExaminedCount(changes_examined)
    for change_a, change_b in differences:
      values_a = result_values[change_a]
      values_b = result_values[change_b]
      bug_update_builder.AddDifference(change_b, values_a, values_b)

    deferred.defer(
        job_bug_update.UpdatePostAndMergeDeferred,
        bug_update_builder,
        self.bug_id,
        self.tags,
        self.url,
        self.project,
        _retry_options=RETRY_OPTIONS)

  def _UpdateGerritIfNeeded(self, success=True):
    if self.gerrit_server and self.gerrit_change_id:
      icon = _ROUND_PUSHPIN if success else _CRYING_CAT_FACE
      state = 'complete' if success else 'failed'
      deferred.defer(
          _UpdateGerritDeferred,
          self.gerrit_server,
          self.gerrit_change_id,
          '%s Job %s.\n\nSee results at: %s' % (icon, state, self.url),
          _retry_options=RETRY_OPTIONS,
      )

  def Fail(self, exception=None):
    # Short-circuit jobs failure updates when we are not the first one to mark a
    # job done.
    first_done = MarkDone(self.job_id)
    if self.use_execution_engine and not first_done:
      return

    # Set these explicitly on this instance, since we know that at this point
    # the job has already been marked done in storage.
    if not self.started:
      self.started = True
      self.started_time = datetime.datetime.utcnow()

    self.done = True

    if not self.cancelled:
      # What follows are the details we are providing when posting updates to the
      # associated bug.
      tb = traceback.format_exc() or ''
      title = _CRYING_CAT_FACE + ' Pinpoint job stopped with an error.'
      exc_info = sys.exc_info()
      if exception is None:
        if exc_info[1] is None:
          # We've been called without a exception in sys.exc_info or in our args.
          # This should not happen.
          exception = errors.JobError('Unknown job error')
          exception.category = 'pinpoint'
        else:
          exception = exc_info[1]
      exc_message = exception.message
      category = None
      if isinstance(exception, errors.JobError):
        category = exception.category

      self.exception_details = {
          'message': exc_message,
          'traceback': tb,
          'category': category,
      }
    self.task = None
    self.put()

    if not self.cancelled:
      comment = '\n'.join((title, self.url, '', exc_message))

      deferred.defer(
          _PostBugCommentDeferred,
          self.bug_id,
          comment,
          project=self.project,
          labels=job_bug_update.ComputeLabelUpdates(['Pinpoint-Job-Failed']),
          send_email=True,
          _retry_options=RETRY_OPTIONS,
      )
      self._UpdateGerritIfNeeded(success=False)
    scheduler.Complete(self)

  def _Schedule(self, countdown=_TASK_INTERVAL):
    # Set a task name to deduplicate retries. This adds some latency, but we're
    # not latency-sensitive. If Job.Run() works asynchronously in the future,
    # we don't need to worry about duplicate tasks.
    # https://github.com/catapult-project/catapult/issues/3900
    task_name = str(uuid.uuid4())
    try:
      task = taskqueue.add(
          queue_name='job-queue',
          url='/api/run/' + self.job_id,
          name=task_name,
          countdown=countdown)
    except (apiproxy_errors.DeadlineExceededError,
            taskqueue.TransientError) as exc:
      raise errors.RecoverableError(exc)

    self.task = task.name

  def _MaybeScheduleRetry(self):
    if not hasattr(self, 'retry_count') or self.retry_count is None:
      self.retry_count = 0

    if self.retry_count >= _MAX_RECOVERABLE_RETRIES:
      return False

    self.retry_count += 1

    # Back off exponentially
    self._Schedule(countdown=_TASK_INTERVAL * (2**self.retry_count))

    return True

  def Run(self):
    """Runs this Job.

    Loops through all Attempts and checks the status of each one, kicking off
    tasks as needed. Does not block to wait for all tasks to finish. Also
    compares adjacent Changes' results and adds any additional Attempts or
    Changes as needed. If there are any incomplete tasks, schedules another
    Run() call on the task queue.
    """
    self.exception_details = None  # In case the Job succeeds on retry.
    self.task = None  # In case an exception is thrown.

    try:
      if scheduler.IsStopped(self):
        # When a user manually cancels a Pinpoint job, job.Cancel() is
        # executed, but it is possible for job.Run() to execute simultaneously,
        # causing a race condition. This if statement takes an extra step to
        # ensure the job stops running after a user cancels the job.
        self.cancelled = True
        logging.debug('Pinpoint job forced to stop because job meets cancellation conditions')
        raise errors.BuildCancelled('Pinpoint Job cancelled')
      if self.use_execution_engine:
        # Treat this as if it's a poll, and run the handler here.
        context = task_module.Evaluate(
            self,
            event_module.Event(type='initiate', target_task=None, payload={}),
            task_evaluator.ExecutionEngine(self))
        result_status = context.get('performance_bisection', {}).get('status')
        if result_status not in {'failed', 'completed'}:
          return

        if result_status == 'failed':
          execution_errors = context['find_culprit'].get('errors', [])
          if execution_errors:
            self.exception_details = execution_errors[0]

        self._Complete()
        return

      if not self._IsTryJob():
        self.state.Explore()
      work_left = self.state.ScheduleWork()

      # Schedule moar task.
      if work_left:
        self._Schedule()
      else:
        self._Complete()

      self.retry_count = 0
    except errors.RecoverableError as e:
      try:
        if not self._MaybeScheduleRetry():
          self.Fail(errors.JobRetryLimitExceededError(wrapped_exc=e))
      except errors.RecoverableError as e:
        self.Fail(errors.JobRetryFailed(wrapped_exc=e))
    except BaseException:
      self.Fail()
      raise
    finally:
      # Don't use `auto_now` for `updated`. When we do data migration, we need
      # to be able to modify the Job without changing the Job's completion time.
      self.updated = datetime.datetime.now()

      if self.completed:
        timing_record.RecordJobTiming(self)

      try:
        self.put()
      except (datastore_errors.Timeout,
              datastore_errors.TransactionFailedError):
        # Retry once.
        self.put()
      except datastore_errors.BadRequestError:
        if self.task:
          queue = taskqueue.Queue('job-queue')
          queue.delete_tasks(taskqueue.Task(name=self.task))
        self.task = None

        # The _JobState is too large to fit in an ndb property.
        # Load the Job from before we updated it, and fail it.
        job = self.key.get(use_cache=False)
        job.task = None
        job.Fail()
        job.updated = datetime.datetime.now()
        job.put()
        raise

  def AsDict(self, options=None):
    def IsoFormatOrNone(attr):
      time = getattr(self, attr, None)
      if time:
        return time.isoformat()
      return None

    d = {
        'job_id': self.job_id,
        'configuration': self.configuration,
        'results_url': self.results_url,
        'arguments': self.arguments,
        'bug_id': self.bug_id,
        'project': self.project,
        'comparison_mode': self.comparison_mode,
        'name': self.auto_name,
        'user': self.user,
        'created': IsoFormatOrNone('created'),
        'updated': IsoFormatOrNone('updated'),
        'started_time': IsoFormatOrNone('started_time'),
        'difference_count': self.difference_count,
        'exception': self.exception_details_dict,
        'status': self.status,
        'cancel_reason': self.cancel_reason,
        'batch_id': self.batch_id,
    }

    if not options:
      return d

    if OPTION_STATE in options or OPTION_INPUTS in options:
      if self.use_execution_engine:
        d.update(
            task_module.Evaluate(
                self,
                event_module.Event(
                    type='serialize', target_task=None, payload={}),
                job_serializer.Serializer()) or {})
      else:
        d.update(self.state.AsDict(options))
    if OPTION_ESTIMATE in options and not self.started:
      d.update(self._GetRunTimeEstimate())
    if OPTION_TAGS in options:
      d['tags'] = {'tags': self.tags}
    return d

  def _GetRunTimeEstimate(self):
    result = timing_record.GetSimilarHistoricalTimings(self)
    if not result:
      return {}

    timings = [t.total_seconds() for t in result.timings]
    return {
        'estimate': {
            'timings': timings,
            'tags': result.tags
        },
        'queue_stats': scheduler.QueueStats(self.configuration)
    }

  def Cancel(self, user, reason):
    # We cannot cancel an already cancelled job.
    if self.cancelled:
      logging.warning(
          'Attempted to cancel a cancelled job "%s"; user = %s, reason = %s',
          self.job_id, user, reason)
      raise errors.CancelError('Job already cancelled.')

    if not scheduler.Cancel(self):
      raise errors.CancelError('Scheduler failed to cancel job.')

    self.cancelled = True
    self.cancel_reason = '{}: {}'.format(user, reason)
    self.updated = datetime.datetime.now()

    # Remove any "task" identifiers.
    self.task = None
    self.put()
    title = _ROUND_PUSHPIN + ' Pinpoint job cancelled.'
    comment = u'{}\n{}\n\nCancelled by {}, reason given: {}'.format(
        title, self.url, user, reason)
    deferred.defer(
        _PostBugCommentDeferred,
        self.bug_id,
        comment,
        project=self.project,
        send_email=True,
        labels=job_bug_update.ComputeLabelUpdates(['Pinpoint-Job-Cancelled']),
        _retry_options=RETRY_OPTIONS)


def _PostBugCommentDeferred(bug_id, *args, **kwargs):
  if not bug_id:
    return

  issue_tracker = issue_tracker_service.IssueTrackerService(
      utils.ServiceAccountHttp())
  issue_tracker.AddBugComment(bug_id, *args, **kwargs)


def _UpdateGerritDeferred(*args, **kwargs):
  gerrit_service.PostChangeComment(*args, **kwargs)
