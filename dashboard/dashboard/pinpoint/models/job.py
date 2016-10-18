# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import quest


def JobFromId(job_id):
  """Get a Job object from its ID. Its ID is currently just its urlsafe key.

  Users of Job should not have to import ndb. This function maintains an
  abstraction layer that separates users from the Datastore details.
  """
  job_key = ndb.Key(urlsafe=job_id)
  return job_key.get()


class Job(ndb.Model):
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

  # What Changes to run.
  # A Change may be added by the user or by the bisect algorithm at any time.
  changes = ndb.LocalStructuredProperty(change.Change, repeated=True)

  # What work needs to be done on each Change. This is fixed at Job creation.
  quests = ndb.LocalStructuredProperty(quest.Quest, repeated=True)
