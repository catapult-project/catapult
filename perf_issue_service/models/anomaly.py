# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.cloud import ndb


class Anomaly(ndb.Model):
  """Represents a change-point or step found in the data series for a test.

  An Anomaly can be an upward or downward change, and can represent an
  improvement or a regression.
  """
  # Whether the alert should only be viewable by internal users.
  internal_only = ndb.BooleanProperty(indexed=True, default=False)

  # The time the alert fired.
  timestamp = ndb.DateTimeProperty(indexed=True, auto_now_add=True)

  # This is the project to which an anomaly is associated with, in the issue
  # tracker service.
  project_id = ndb.StringProperty(indexed=True, default='chromium')

  # AlertGroups used for grouping
  groups = ndb.KeyProperty(indexed=True, repeated=True)

  # This field aims to replace the 'bug_id' field serving as a state indicator.
  state = ndb.StringProperty(
      default='untriaged',
      choices=['untriaged', 'triaged', 'ignored', 'invalid'])

  subscription_names = ndb.StringProperty(indexed=True, repeated=True)

  anomaly_config = ndb.JsonProperty()

  # Each Alert is related to one Test.
  test = ndb.KeyProperty(indexed=True)
  statistic = ndb.StringProperty(indexed=True)

  # Each Alert has a revision range it's associated with; however,
  # start_revision and end_revision could be the same.
  start_revision = ndb.IntegerProperty(indexed=True)
  end_revision = ndb.IntegerProperty(indexed=True)


  # Whether this anomaly represents an improvement; if false, this anomaly is
  # considered to be a regression.
  is_improvement = ndb.BooleanProperty(indexed=True, default=False)

  # Whether this anomaly recovered (i.e. if this is a step down, whether there
  # is a corresponding step up later on, or vice versa.)
  recovered = ndb.BooleanProperty(indexed=True, default=False)
