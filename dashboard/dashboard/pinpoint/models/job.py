# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from dashboard.models import internal_only_model


def JobFromId(job_id):
  job_key = ndb.Key(urlsafe=job_id)
  return job_key.get()


class Dep(ndb.Model):
  repository = ndb.StringProperty(required=True)
  git_hash = ndb.StringProperty(required=True)


class Change(ndb.Model):
  deps = ndb.StructuredProperty(Dep, required=True, repeated=True)
  patch = ndb.StringProperty()  # TODO: Placeholder.


class Task(ndb.Model):
  # The ID given to the task in its Distributor.
  # If it is a local task, task_id is 0.
  # If it is a Swarming task, task_id is [a-z0-9]{16}.
  # If it is a Buildbucket task, task_id is [0-9]{19}.
  task_id = ndb.StringProperty(required=True)

  created = ndb.DateTimeProperty(required=True, auto_now_add=True)
  updated = ndb.DateTimeProperty(required=True, auto_now=True)

  change = ndb.StructuredProperty(Change, required=True)
  results = ndb.FloatProperty(repeated=True)


class Job(internal_only_model.InternalOnlyModel):
  internal_only = ndb.BooleanProperty()
  created = ndb.DateTimeProperty(required=True, auto_now_add=True)
  updated = ndb.DateTimeProperty(required=True, auto_now=True)

  # Request parameters.
  configuration = ndb.StringProperty(required=True)
  changes = ndb.StructuredProperty(Change, required=True, repeated=True)
  test_suite = ndb.StringProperty()
  test = ndb.StringProperty()
  metric = ndb.StringProperty()

  # State.
  # TODO: Flesh out the state fields.
  hostname = ndb.StringProperty()
  tasks = ndb.KeyProperty(kind=Task, repeated=True)
