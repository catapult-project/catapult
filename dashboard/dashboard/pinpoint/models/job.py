# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import datetime
import itertools
import logging
import os
import re
import traceback
import uuid

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.runtime import apiproxy_errors

from dashboard.common import utils
from dashboard.pinpoint.models import attempt as attempt_module
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import kolmogorov_smirnov
from dashboard.pinpoint.models import mann_whitney_u
from dashboard.services import issue_tracker_service


# We want this to be fast to minimize overhead while waiting for tasks to
# finish, but don't want to consume too many resources.
_TASK_INTERVAL = 10

# The questionable significance levels are determined by first picking two
# representative samples of size 10. Take their p-value. Then repeat for each i,
# multiplying the sample size by i. To calculate these values:
# import math
# from dashboard.pinpoint.models import mann_whitney_u
# a = [0] * 10
# b = [0] * 9 + [1]
# print 1
# for i in xrange(1, 10):
#   pvalue = mann_whitney_u.MannWhitneyU(a * i, b * i)
#   print math.ceil(pvalue * 10000) / 10000
_QUESTIONABLE_SIGNIFICANCE_LEVELS = (
    1.0000, 0.3682, 0.1625, 0.0815, 0.0428, 0.0230,
    0.0126, 0.0070, 0.0039, 0.0022, 0.0013, 0.0007,
)
_SIGNIFICANCE_LEVEL = 0.001
_REPEAT_COUNT_INCREASE = 10


_DIFFERENT = 'different'
_PENDING = 'pending'
_SAME = 'same'
_UNKNOWN = 'unknown'


_CRYING_CAT_FACE = u'\U0001f63f'
_MIDDLE_DOT = u'\xb7'
_ROUND_PUSHPIN = u'\U0001f4cd'


def JobFromId(job_id):
  """Get a Job object from its ID. Its ID is just its key as a hex string.

  Users of Job should not have to import ndb. This function maintains an
  abstraction layer that separates users from the Datastore details.
  """
  job_key = ndb.Key('Job', int(job_id, 16))
  return job_key.get()


class Job(ndb.Model):
  """A Pinpoint job."""

  created = ndb.DateTimeProperty(required=True, auto_now_add=True)
  # Don't use `auto_now` for `updated`. When we do data migration, we need
  # to be able to modify the Job without changing the Job's completion time.
  updated = ndb.DateTimeProperty(required=True, auto_now_add=True)

  # The name of the Task Queue task this job is running on. If it's present, the
  # job is running. The task is also None for Task Queue retries.
  task = ndb.StringProperty()

  # The string contents of any Exception that was thrown to the top level.
  # If it's present, the job failed.
  exception = ndb.TextProperty()

  # Request parameters.
  arguments = ndb.JsonProperty(required=True)

  # If True, the service should pick additional Changes to run (bisect).
  # If False, only run the Changes explicitly added by the user.
  auto_explore = ndb.BooleanProperty(required=True)

  # TODO: The bug id is only used for posting bug comments when a job starts and
  # completes. This probably should not be the responsibility of Pinpoint.
  bug_id = ndb.IntegerProperty()

  state = ndb.PickleProperty(required=True, compressed=True)

  @classmethod
  def New(cls, arguments, quests, auto_explore, bug_id=None):
    # Create job.
    return cls(
        arguments=arguments,
        auto_explore=auto_explore,
        bug_id=bug_id,
        state=_JobState(quests))

  @property
  def job_id(self):
    return '%x' % self.key.id()

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
    self._Schedule()

    title = _ROUND_PUSHPIN + ' Pinpoint job started.'
    comment = '\n'.join((title, self.url))
    self._PostBugComment(comment, send_email=False)

  def _Complete(self):
    # Format bug comment.
    differences = tuple(self.state.Differences())

    if not differences:
      title = "<b>%s Couldn't reproduce a difference.</b>" % _ROUND_PUSHPIN
      self._PostBugComment('\n'.join((title, self.url)))
      return

    # Include list of Changes.
    owner = None
    cc_list = set()
    commit_details = []
    for _, change in differences:
      commit_info = change.last_commit.Details()

      author = commit_info['author']['email']
      owner = author  # TODO: Assign the largest difference, not the last one.
      cc_list.add(author)
      cc_list |= frozenset(re.findall('Reviewed-by: .+ <(.+)>',
                                      commit_info['message']))
      commit_details.append(_FormatCommitForBug(
          change.last_commit, commit_info))

    # Header.
    if len(differences) == 1:
      status = 'Found a significant difference after 1 commit.'
    else:
      status = ('Found significant differences after each of %d commits.' %
                len(differences))

    title = '<b>%s %s</b>' % (_ROUND_PUSHPIN, status)
    header = '\n'.join((title, self.url))

    # Body.
    body = '\n\n'.join(commit_details)

    # Footer.
    footer = ('Understanding performance regressions:\n'
              '  http://g.co/ChromePerformanceRegressions')

    # Bring it all together.
    comment = '\n\n'.join((header, body, footer))
    self._PostBugComment(comment, status='Assigned',
                         cc_list=sorted(cc_list), owner=owner)

  def _Fail(self):
    self.exception = traceback.format_exc()

    title = _CRYING_CAT_FACE + ' Pinpoint job stopped with an error.'
    comment = '\n'.join((title, self.url))
    self._PostBugComment(comment)

  def _Schedule(self):
    # Set a task name to deduplicate retries. This adds some latency, but we're
    # not latency-sensitive. If Job.Run() works asynchronously in the future,
    # we don't need to worry about duplicate tasks.
    # https://github.com/catapult-project/catapult/issues/3900
    task_name = str(uuid.uuid4())
    try:
      task = taskqueue.add(
          queue_name='job-queue', url='/api/run/' + self.job_id,
          name=task_name, countdown=_TASK_INTERVAL)
    except apiproxy_errors.DeadlineExceededError:
      task = taskqueue.add(
          queue_name='job-queue', url='/api/run/' + self.job_id,
          name=task_name, countdown=_TASK_INTERVAL)

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
        self._Schedule()
      else:
        self._Complete()
    except BaseException:
      self._Fail()
      raise
    finally:
      # Don't use `auto_now` for `updated`. When we do data migration, we need
      # to be able to modify the Job without changing the Job's completion time.
      self.updated = datetime.datetime.now()

  def AsDict(self, include_state=True):
    d = {
        'job_id': self.job_id,

        'arguments': self.arguments,
        'auto_explore': self.auto_explore,
        'bug_id': self.bug_id,

        'created': self.created.isoformat(),
        'updated': self.updated.isoformat(),
        'exception': self.exception,
        'status': self.status,
    }
    if include_state:
      d.update(self.state.AsDict())
    return d

  def _PostBugComment(self, *args, **kwargs):
    if not self.bug_id:
      return

    issue_tracker = issue_tracker_service.IssueTrackerService(
        utils.ServiceAccountHttp())
    issue_tracker.AddBugComment(self.bug_id, *args, **kwargs)


class _JobState(object):
  """The internal state of a Job.

  Wrapping the entire internal state of a Job in a PickleProperty allows us to
  use regular Python objects, with constructors, dicts, and object references.

  We lose the ability to index and query the fields, but it's all internal
  anyway. Everything queryable should be on the Job object.
  """

  def __init__(self, quests):
    """Create a _JobState.

    Args:
      quests: A sequence of quests to run on each Change.
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

  def AddAttempts(self, change):
    assert change in self._attempts
    for _ in xrange(_REPEAT_COUNT_INCREASE):
      self._attempts[change].append(
          attempt_module.Attempt(self._quests, change))

  def AddChange(self, change, index=None):
    if index:
      self._changes.insert(index, change)
    else:
      self._changes.append(change)

    self._attempts[change] = []
    self.AddAttempts(change)

  def Explore(self):
    """Compare Changes and bisect by adding additional Changes as needed.

    For every pair of adjacent Changes, compare their results as probability
    distributions. If the results are different, find the midpoint of the
    Changes and add it to the Job. If the results are the same, do nothing.
    If the results are inconclusive, add more Attempts to the Change with fewer
    Attempts until we decide they are the same or different.

    The midpoint can only be added if the second Change represents a commit that
    comes after the first Change. Otherwise, this method won't explore further.
    For example, if Change A is repo@abc, and Change B is repo@abc + patch,
    there's no way to pick additional Changes to try.
    """
    # This loop adds Changes to the _changes list while looping through it.
    # The Change insertion simultaneously uses and modifies the list indices.
    # However, the loop index goes in reverse order and Changes are only added
    # after the loop index, so the loop never encounters the modified items.
    for index in xrange(len(self._changes) - 1, 0, -1):
      change_a = self._changes[index - 1]
      change_b = self._changes[index]
      comparison = self._Compare(change_a, change_b)

      if comparison == _DIFFERENT:
        try:
          midpoint = change_module.Change.Midpoint(change_a, change_b)
        except change_module.NonLinearError:
          continue

        logging.info('Adding Change %s.', midpoint)
        self.AddChange(midpoint, index)

      elif comparison == _UNKNOWN:
        if len(self._attempts[change_a]) <= len(self._attempts[change_b]):
          self.AddAttempts(change_a)
        else:
          self.AddAttempts(change_b)

  def ScheduleWork(self):
    work_left = False
    for attempts in self._attempts.itervalues():
      for attempt in attempts:
        if attempt.completed:
          continue

        attempt.ScheduleWork()
        work_left = True

    return work_left

  def Differences(self):
    """Compares every pair of Changes and yields ones with different results.

    This method loops through every pair of adjacent Changes. If they have
    statistically different results, this method yields the latter one (which is
    assumed to have caused the difference).

    Yields:
      Tuples of (change_index, Change).
    """
    for index in xrange(1, len(self._changes)):
      change_a = self._changes[index - 1]
      change_b = self._changes[index]
      if self._Compare(change_a, change_b) == _DIFFERENT:
        yield index, change_b

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
      executions = _ExecutionsPerQuest(self._attempts[change])
      change_result_values = []
      for quest in self._quests:
        quest_result_values = list(itertools.chain.from_iterable(
            execution.result_values for execution in executions[quest]
            if execution.completed))
        change_result_values.append(quest_result_values)
      result_values.append(change_result_values)

    attempts = []
    for c in self._changes:
      attempts.append([attempt.AsDict() for attempt in self._attempts[c]])

    return {
        'quests': map(str, self._quests),
        'changes': [change.AsDict() for change in self._changes],
        # TODO: Use JobState.Differences().
        'comparisons': comparisons,
        'result_values': result_values,
        'attempts': attempts,
    }

  def _Compare(self, change_a, change_b):
    """Compare the results of two Changes in this Job.

    Aggregate the exceptions and result_values across every Quest for both
    Changes. Then, compare all the results for each Quest. If any of them are
    different, return _DIFFERENT. Otherwise, if any of them are inconclusive,
    return _UNKNOWN.  Otherwise, they are the _SAME.

    Arguments:
      change_a: The first Change whose results to compare.
      change_b: The second Change whose results to compare.

    Returns:
      _PENDING: If either Change has an incomplete Attempt.
      _DIFFERENT: If the two Changes (very likely) have different results.
      _SAME: If the two Changes (probably) have the same result.
      _UNKNOWN: If we'd like more data to make a decision.
    """
    attempts_a = self._attempts[change_a]
    attempts_b = self._attempts[change_b]

    if any(not attempt.completed for attempt in attempts_a + attempts_b):
      return _PENDING

    executions_by_quest_a = _ExecutionsPerQuest(attempts_a)
    executions_by_quest_b = _ExecutionsPerQuest(attempts_b)

    any_unknowns = False
    for quest in self._quests:
      executions_a = executions_by_quest_a[quest]
      executions_b = executions_by_quest_b[quest]

      # Compare exceptions.
      values_a = tuple(bool(execution.exception) for execution in executions_a)
      values_b = tuple(bool(execution.exception) for execution in executions_b)
      if values_a and values_b:
        comparison = _CompareValues(values_a, values_b)
        if comparison == _DIFFERENT:
          return _DIFFERENT
        elif comparison == _UNKNOWN:
          any_unknowns = True

      # Compare result values.
      values_a = tuple(_Mean(execution.result_values)
                       for execution in executions_a if execution.result_values)
      values_b = tuple(_Mean(execution.result_values)
                       for execution in executions_b if execution.result_values)
      if values_a and values_b:
        comparison = _CompareValues(values_a, values_b)
        if comparison == _DIFFERENT:
          return _DIFFERENT
        elif comparison == _UNKNOWN:
          any_unknowns = True

    if any_unknowns:
      return _UNKNOWN

    return _SAME


def _FormatCommitForBug(commit, commit_info):
  subject = '<b>%s</b>' % commit_info['message'].split('\n', 1)[0]
  author = commit_info['author']['email']
  time = commit_info['committer']['time']

  byline = 'By %s %s %s' % (author, _MIDDLE_DOT, time)
  git_link = commit.repository + ' @ ' + commit.git_hash
  return '\n'.join((subject, byline, git_link))


def _ExecutionsPerQuest(attempts):
  executions = collections.defaultdict(list)
  for attempt in attempts:
    for quest, execution in zip(attempt.quests, attempt.executions):
      executions[quest].append(execution)
  return executions


def _CompareValues(values_a, values_b):
  """Decide whether two samples are the same, different, or unknown.

  Arguments:
    values_a: A list of sortable values. They don't need to be numeric.
    values_b: A list of sortable values. They don't need to be numeric.

  Returns:
    _DIFFERENT: The samples likely come from different distributions.
        Reject the null hypothesis.
    _SAME: Not enough evidence to say that the samples come from different
        distributions. Fail to reject the null hypothesis.
    _UNKNOWN: Not enough evidence to say that the samples come from different
        distributions, but it looks a little suspicious, and we would like more
        data before making a final decision.
  """
  if not (values_a and values_b):
    # A sample has no values in it.
    return _UNKNOWN

  # MWU is bad at detecting changes in variance, and K-S is bad with discrete
  # distributions. So use both. We want low p-values for the below examples.
  #        a                     b               MWU(a, b)  KS(a, b)
  # [0]*20            [0]*15+[1]*5                0.0097     0.4973
  # range(10, 30)     range(10)+range(30, 40)     0.4946     0.0082
  p_value = min(
      kolmogorov_smirnov.KolmogorovSmirnov(values_a, values_b),
      mann_whitney_u.MannWhitneyU(values_a, values_b))

  if p_value < _SIGNIFICANCE_LEVEL:
    # The p-value is less than the significance level. Reject the null
    # hypothesis.
    return _DIFFERENT

  index = min(len(values_a), len(values_b)) / 10
  questionable_significance_level = _QUESTIONABLE_SIGNIFICANCE_LEVELS[index]
  if p_value < questionable_significance_level:
    # The p-value is not less than the significance level, but it's small enough
    # to be suspicious. We'd like to investigate more closely.
    return _UNKNOWN

  # The p-value is quite large. We're not suspicious that the two samples might
  # come from different distributions, and we don't care to investigate more.
  return _SAME


def _Mean(values):
  return float(sum(values)) / len(values)
