# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import os

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard.common import utils
from dashboard.pinpoint import mann_whitney_u
from dashboard.pinpoint.models import attempt as attempt_module
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import quest as quest_module
from dashboard.services import issue_tracker_service


# We want this to be fast to minimize overhead while waiting for tasks to
# finish, but don't want to consume too many resources.
_TASK_INTERVAL = 10


_DEFAULT_REPEAT_COUNT = 10
_DEFAULT_ATTEMPT_COUNT = 1
_SIGNIFICANCE_LEVEL = 0.01


_DIFFERENT = 'different'
_PENDING = 'pending'
_SAME = 'same'
_UNKNOWN = 'unknown'


def JobFromId(job_id):
  """Get a Job object from its ID. Its ID is just its urlsafe key.

  Users of Job should not have to import ndb. This function maintains an
  abstraction layer that separates users from the Datastore details.
  """
  job_key = ndb.Key(urlsafe=job_id)
  return job_key.get()


class Job(ndb.Model):
  """A Pinpoint job."""

  created = ndb.DateTimeProperty(required=True, auto_now_add=True)
  updated = ndb.DateTimeProperty(required=True, auto_now=True)

  # The name of the Task Queue task this job is running on. If it's present, the
  # job is running. The task is also None for Task Queue retries.
  task = ndb.StringProperty()

  # The string contents of any Exception that was thrown to the top level.
  # If it's present, the job failed.
  exception = ndb.StringProperty()

  # Request parameters.
  configuration = ndb.StringProperty(required=True)
  test_suite = ndb.StringProperty()
  test = ndb.StringProperty()
  metric = ndb.StringProperty()

  # If True, the service should pick additional Changes to run (bisect).
  # If False, only run the Changes explicitly added by the user.
  auto_explore = ndb.BooleanProperty(required=True)

  # TODO: The bug id is only used for posting bug comments when a job starts and
  # completes. This probably should not be the responsibility of Pinpoint.
  bug_id = ndb.IntegerProperty()

  state = ndb.PickleProperty(required=True)

  @classmethod
  def New(cls, configuration, test_suite, test, metric, auto_explore, bug_id):
    # Get list of quests.
    quests = [quest_module.FindIsolate(configuration)]
    if test_suite:
      quests.append(quest_module.RunTest(configuration, test_suite, test,
                                         _DEFAULT_REPEAT_COUNT))
    if metric:
      quests.append(quest_module.ReadValue(metric, test))

    # Create job.
    return cls(
        configuration=configuration,
        test_suite=test_suite,
        test=test,
        metric=metric,
        auto_explore=auto_explore,
        bug_id=bug_id,
        state=_JobState(quests, _DEFAULT_ATTEMPT_COUNT))

  @property
  def job_id(self):
    return self.key.urlsafe()

  @property
  def status(self):
    if self.task:
      return 'Running'

    if self.exception:
      return 'Failed'

    return 'Completed'

  @property
  def url(self):
    return 'https://%s/job/%s' % (os.environ['HTTP_HOST'], self.job_id)

  def AddChange(self, change):
    self.state.AddChange(change)

  def Start(self):
    self.Schedule()

    comment = 'Pinpoint job started.\n' + self.url
    issue_tracker = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
    issue_tracker.AddBugComment(self.bug_id, comment, send_email=False)

  def Complete(self):
    comment = 'Pinpoint job complete!\n' + self.url
    issue_tracker = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
    issue_tracker.AddBugComment(self.bug_id, comment, send_email=False)

  def Fail(self, exception):
    self.exception = str(exception)

    comment = 'Pinpoint job failed!\n' + self.url
    issue_tracker = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
    issue_tracker.AddBugComment(self.bug_id, comment, send_email=False)

  def Schedule(self):
    task = taskqueue.add(queue_name='job-queue', url='/api/run/' + self.job_id,
                         countdown=_TASK_INTERVAL)
    self.task = task.name

  def Run(self):
    self.exception = None  # In case the Job succeeds on retry.
    self.task = None  # In case an exception is thrown.

    try:
      if self.auto_explore:
        self.state.Explore()
      work_left = self.state.ScheduleWork()

      # Schedule moar task.
      if work_left:
        self.Schedule()
      else:
        self.Complete()
    except BaseException as e:
      self.Fail(e)
      raise

  def AsDict(self):
    return {
        'job_id': self.job_id,

        'configuration': self.configuration,
        'test_suite': self.test_suite,
        'test': self.test,
        'metric': self.metric,
        'auto_explore': self.auto_explore,

        'created': self.created.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'updated': self.updated.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'status': self.status,

        'state': self.state.AsDict(),
    }


class _JobState(object):
  """The internal state of a Job.

  Wrapping the entire internal state of a Job in a PickleProperty allows us to
  use regular Python objects, with constructors, dicts, and object references.

  We lose the ability to index and query the fields, but it's all internal
  anyway. Everything queryable should be on the Job object.
  """

  def __init__(self, quests, attempt_count):
    """Create a _JobState.

    Args:
      quests: A sequence of quests to run on each Change.
      attempt_count: The max number of attempts to automatically run per Change.
    """
    # _quests is mutable. Any modification should mutate the existing list
    # in-place rather than assign a new list, because every Attempt references
    # this object and will be updated automatically if it's mutated.
    self._quests = list(quests)

    # _changes can be in arbitrary order. Client should not assume that the
    # list of Changes is sorted in any particular order.
    self._changes = []

    # A mapping from a Change to a list of Attempts on that Change.
    self._attempts = {}

    self._attempt_count = attempt_count

  def AddAttempt(self, change):
    assert change in self._attempts
    self._attempts[change].append(attempt_module.Attempt(self._quests, change))

  def AddChange(self, change, index=None):
    if index:
      self._changes.insert(index, change)
    else:
      self._changes.append(change)
    self._attempts[change] = []
    self.AddAttempt(change)

  def Explore(self):
    """Compare Changes and bisect by adding additional Changes as needed.

    For every pair of adjacent Changes, compare their results as probability
    distributions. If more information is needed to establish statistical
    confidence, add an additional Attempt. If the results are different, find
    the midpoint of the Changes and add it to the Job.

    The midpoint can only be added if the second Change represents a commit that
    comes after the first Change. Otherwise, this method won't explore further.
    For example, if Change A is repo@abc, and Change B is repo@abc + patch,
    there's no way to pick additional Changes to try.
    """
    # Compare every pair of Changes.
    # TODO: The list may Change while iterating through it.
    for index in xrange(1, len(self._changes)):
      change_a = self._changes[index - 1]
      change_b = self._changes[index]

      comparison_result = self._Compare(change_a, change_b)
      if comparison_result == _DIFFERENT:
        # Different: Bisect and add an additional Change to the job.
        try:
          midpoint = change_module.Change.Midpoint(change_a, change_b)
        except change_module.NonLinearError:
          midpoint = None
        if midpoint:
          logging.info('Adding Change %s.', midpoint)
          self.AddChange(midpoint, index)
      elif comparison_result == _SAME:
        # The same: Do nothing.
        continue
      elif comparison_result == _UNKNOWN:
        # Unknown: Add an Attempt to the Change with the fewest Attempts.
        change = min(change_a, change_b, key=lambda c: len(self._attempts[c]))
        self.AddAttempt(change)

  def ScheduleWork(self):
    work_left = False
    for attempts in self._attempts.itervalues():
      for attempt in attempts:
        if attempt.completed:
          continue

        attempt.ScheduleWork()
        work_left = True

    return work_left

  def AsDict(self):
    comparisons = []
    for index in xrange(1, len(self._changes)):
      change_a = self._changes[index - 1]
      change_b = self._changes[index]
      comparisons.append(self._Compare(change_a, change_b))

    # result_values is a 3D array. result_values[change][quest] is a list of
    # all the result values for that Change and Quest.
    result_values = []
    for change in self._changes:
      change_result_values = []

      change_results_per_quest = _CombineResultsPerQuest(self._attempts[change])
      for quest in self._quests:
        change_result_values.append(change_results_per_quest[quest])

      result_values.append(change_result_values)

    return {
        'quests': map(str, self._quests),
        'changes': map(str, self._changes),
        'comparisons': comparisons,
        'result_values': result_values,
    }

  def _Compare(self, change_a, change_b):
    attempts_a = self._attempts[change_a]
    attempts_b = self._attempts[change_b]

    if any(not attempt.completed for attempt in attempts_a + attempts_b):
      return _PENDING

    results_a = _CombineResultsPerQuest(attempts_a)
    results_b = _CombineResultsPerQuest(attempts_b)

    if any(_CompareResults(results_a[quest], results_b[quest]) == _DIFFERENT
           for quest in self._quests):
      return _DIFFERENT

    # Here, "the same" means that we fail to reject the null hypothesis. We can
    # never be completely sure that the two Changes have the same results, but
    # we've run everything that we planned to, and didn't detect any difference.
    if (len(attempts_a) >= self._attempt_count and
        len(attempts_b) >= self._attempt_count):
      return _SAME

    return _UNKNOWN


def _CombineResultsPerQuest(attempts):
  aggregate_results = collections.defaultdict(list)
  for attempt in attempts:
    if not attempt.completed:
      continue

    for quest, results in attempt.result_values.iteritems():
      aggregate_results[quest] += results

  return aggregate_results


def _CompareResults(results_a, results_b):
  if len(results_a) == 0 or len(results_b) == 0:
    return _UNKNOWN

  try:
    p_value = mann_whitney_u.MannWhitneyU(results_a, results_b)
  except ValueError:
    return _UNKNOWN

  if p_value < _SIGNIFICANCE_LEVEL:
    return _DIFFERENT
  else:
    return _UNKNOWN
