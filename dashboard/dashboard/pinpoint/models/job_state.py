# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging

from dashboard.common import math_utils
from dashboard.pinpoint.models import attempt as attempt_module
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import compare


_REPEAT_COUNT_INCREASE = 10


FUNCTIONAL = 'functional'
PERFORMANCE = 'performance'
COMPARISON_MODES = (FUNCTIONAL, PERFORMANCE)


class JobState(object):
  """The internal state of a Job.

  Wrapping the entire internal state of a Job in a PickleProperty allows us to
  use regular Python objects, with constructors, dicts, and object references.

  We lose the ability to index and query the fields, but it's all internal
  anyway. Everything queryable should be on the Job object."""

  def __init__(self, quests, comparison_mode=None,
               comparison_magnitude=None, pin=None):
    """Create a JobState.

    Args:
      comparison_mode: Either 'functional' or 'performance', which the Job uses
          to figure out whether to perform a functional or performance bisect.
          If None, the Job will not automatically add any Attempts or Changes.
      comparison_magnitude: The estimated size of the regression or improvement
          to look for. Smaller magnitudes require more repeats.
      quests: A sequence of quests to run on each Change.
      pin: A Change (Commits + Patch) to apply to every Change in this Job.
    """
    # _quests is mutable. Any modification should mutate the existing list
    # in-place rather than assign a new list, because every Attempt references
    # this object and will be updated automatically if it's mutated.
    self._quests = list(quests)

    self._comparison_mode = comparison_mode
    self._comparison_magnitude = comparison_magnitude

    self._pin = pin

    # _changes can be in arbitrary order. Client should not assume that the
    # list of Changes is sorted in any particular order.
    self._changes = []

    # A mapping from a Change to a list of Attempts on that Change.
    self._attempts = {}

  @property
  def comparison_mode(self):
    return self._comparison_mode

  def AddAttempts(self, change):
    if not hasattr(self, '_pin'):
      # TODO: Remove after data migration.
      self._pin = None

    if self._pin:
      change_with_pin = change.Update(self._pin)
    else:
      change_with_pin = change

    for _ in xrange(_REPEAT_COUNT_INCREASE):
      attempt = attempt_module.Attempt(self._quests, change_with_pin)
      self._attempts[change].append(attempt)

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

      if comparison == compare.DIFFERENT:
        try:
          midpoint = change_module.Change.Midpoint(change_a, change_b)
        except change_module.NonLinearError:
          continue

        logging.info('Adding Change %s.', midpoint)
        self.AddChange(midpoint, index)

      elif comparison == compare.UNKNOWN:
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

    if not work_left:
      self._RaiseErrorIfAllAttemptsFailed()

    return work_left

  def _RaiseErrorIfAllAttemptsFailed(self):
    counter = collections.Counter()
    for attempts in self._attempts.itervalues():
      for attempt in attempts:
        if not attempt.exception:
          return
        counter[attempt.exception.splitlines()[-1]] += 1

    most_common_exceptions = counter.most_common(1)
    if not most_common_exceptions:
      return

    exception, exception_count = most_common_exceptions[0]
    attempt_count = sum(counter.itervalues())
    raise Exception(
        'All of the runs failed. The most common error (%d/%d runs) '
        'was:\n%s' % (exception_count, attempt_count, exception))

  def Differences(self):
    """Compares every pair of Changes and yields ones with different results.

    This method loops through every pair of adjacent Changes. If they have
    statistically different results, this method yields the latter one (which is
    assumed to have caused the difference).

    Returns:
      A list of tuples: [(Change_before, Change_after), ...]
    """
    differences = []
    for index in xrange(1, len(self._changes)):
      change_a = self._changes[index - 1]
      change_b = self._changes[index]
      if self._Compare(change_a, change_b) == compare.DIFFERENT:
        differences.append((change_a, change_b))
    return differences

  def AsDict(self):
    state = []
    for change in self._changes:
      state.append({
          'attempts': [attempt.AsDict() for attempt in self._attempts[change]],
          'change': change.AsDict(),
          'comparisons': {},
          'result_values': self.ResultValues(change),
      })

    for index in xrange(1, len(self._changes)):
      comparison = self._Compare(self._changes[index - 1], self._changes[index])
      state[index - 1]['comparisons']['next'] = comparison
      state[index]['comparisons']['prev'] = comparison

    return {
        'comparison_mode': self._comparison_mode,
        'quests': map(str, self._quests),
        'state': state,
    }

  def _Compare(self, change_a, change_b):
    """Compare the results of two Changes in this Job.

    Aggregate the exceptions and result_values across every Quest for both
    Changes. Then, compare all the results for each Quest. If any of them are
    different, return DIFFERENT. Otherwise, if any of them are inconclusive,
    return UNKNOWN.  Otherwise, they are the SAME.

    Arguments:
      change_a: The first Change whose results to compare.
      change_b: The second Change whose results to compare.

    Returns:
      PENDING: If either Change has an incomplete Attempt.
      DIFFERENT: If the two Changes (very likely) have different results.
      SAME: If the two Changes (probably) have the same result.
      UNKNOWN: If we'd like more data to make a decision.
    """
    attempts_a = self._attempts[change_a]
    attempts_b = self._attempts[change_b]

    if any(not attempt.completed for attempt in attempts_a + attempts_b):
      return compare.PENDING

    attempt_count = (len(attempts_a) + len(attempts_b)) / 2

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
        if self._comparison_mode == FUNCTIONAL:
          if (hasattr(self, '_comparison_magnitude') and
              self._comparison_magnitude):
            comparison_magnitude = self._comparison_magnitude
          else:
            comparison_magnitude = 0.5
        else:
          comparison_magnitude = 1.0
        comparison = compare.Compare(values_a, values_b, attempt_count,
                                     FUNCTIONAL, comparison_magnitude)
        if comparison == compare.DIFFERENT:
          return compare.DIFFERENT
        elif comparison == compare.UNKNOWN:
          any_unknowns = True

      # Compare result values.
      values_a = tuple(_Mean(execution.result_values)
                       for execution in executions_a if execution.result_values)
      values_b = tuple(_Mean(execution.result_values)
                       for execution in executions_b if execution.result_values)
      if values_a and values_b:
        if (hasattr(self, '_comparison_magnitude') and
            self._comparison_magnitude):
          max_iqr = max(math_utils.Iqr(values_a), math_utils.Iqr(values_b))
          if max_iqr:
            comparison_magnitude = abs(self._comparison_magnitude / max_iqr)
          else:
            comparison_magnitude = 1000  # Something very large.
        else:
          comparison_magnitude = 1.0
        comparison = compare.Compare(values_a, values_b, attempt_count,
                                     PERFORMANCE, comparison_magnitude)
        if comparison == compare.DIFFERENT:
          return compare.DIFFERENT
        elif comparison == compare.UNKNOWN:
          any_unknowns = True

    if any_unknowns:
      return compare.UNKNOWN

    return compare.SAME

  def ResultValues(self, change):
    quest_index = len(self._quests) - 1
    result_values = []

    if self._comparison_mode == 'functional':
      pass_fails = []
      for attempt in self._attempts[change]:
        if attempt.completed:
          pass_fails.append(int(attempt.failed))
      if pass_fails:
        result_values.append(_Mean(pass_fails))

    elif self._comparison_mode == 'performance':
      for attempt in self._attempts[change]:
        if quest_index < len(attempt.executions):
          result_values += attempt.executions[quest_index].result_values

    return result_values


def _ExecutionsPerQuest(attempts):
  executions = collections.defaultdict(list)
  for attempt in attempts:
    for quest, execution in zip(attempt.quests, attempt.executions):
      executions[quest].append(execution)
  return executions


def _Mean(values):
  return float(sum(values)) / len(values)
