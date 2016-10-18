# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class Attempt(ndb.Model):
  # The ID given to the task in its Distributor.
  # If it is a local task, task_id is 0.
  # If it is a Swarming task, task_id is [a-z0-9]{16}.
  # If it is a Buildbucket task, task_id is [0-9]{19}.
  attempt_id = ndb.StringProperty(required=True)

  created = ndb.DateTimeProperty(required=True, auto_now_add=True)
  updated = ndb.DateTimeProperty(required=True, auto_now=True)

  quest_index = ndb.IntegerProperty(required=True)

  # TODO: replace with a Values JSON.
  results = ndb.FloatProperty(repeated=True)
