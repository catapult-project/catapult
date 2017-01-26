# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard.pinpoint.models import attempt as attempt_module
from dashboard.pinpoint.models import quest


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

  # The name of the Task Queue task this job is running on. If it's not present,
  # the job isn't running.
  task = ndb.StringProperty()

  # Request parameters.
  configuration = ndb.StringProperty(required=True)
  test_suite = ndb.StringProperty()
  test = ndb.StringProperty()
  metric = ndb.StringProperty()

  # If True, the service should pick additional Changes to run (bisect).
  # If False, only run the Changes explicitly added by the user.
  auto_explore = ndb.BooleanProperty(required=True)

  state = ndb.PickleProperty(required=True)

  @classmethod
  def New(cls, configuration, test_suite, test, metric, auto_explore):
    # Get list of quests.
    quests = [quest.FindIsolated(configuration)]
    if test_suite:
      quests.append(quest.RunTest(configuration, test_suite, test))
    if metric:
      quests.append(quest.ReadValue(metric))

    # Create job.
    return cls(
        configuration=configuration,
        test_suite=test_suite,
        test=test,
        metric=metric,
        auto_explore=auto_explore,
        state=_JobState(quests))

  def AddChange(self, change):
    self.state.AddChange(change)

  def Explore(self):
    self.state.Explore()

  def ScheduleWork(self):
    return self.state.ScheduleWork()


class _JobState(object):
  """The internal state of a Job.

  Wrapping the entire internal state of a Job in a PickleProperty allows us to
  use regular Python objects, with constructors, dicts, and object references.

  We lose the ability to index and query the fields, but it's all internal
  anyway. Everything queryable should be on the Job object.
  """

  def __init__(self, quests):
    self._quests = quests
    self._changes = []
    self._attempts = {}

  def AddChange(self, change):
    self._changes.append(change)
    self._attempts[change] = [attempt_module.Attempt(self._quests, change)]

  def Explore(self):
    # TODO: Bisect.
    # Compare every pair of revisions. If they're:
    #   Different: Use gitiles to resolve the revision range and add an
    #              additional Change to the job. Reschedule.
    #   The same, or hit the max repeat count: Do nothing.
    #   Other: Add an additional Attempt to the Change with the fewest
    #          Attempts and reschedule.
    pass

  def ScheduleWork(self):
    work_left = False
    for attempts in self._attempts.itervalues():
      for attempt in attempts:
        if attempt.completed:
          continue

        attempt.ScheduleWork()
        work_left = True

    return work_left
