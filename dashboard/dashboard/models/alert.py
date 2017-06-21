# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A base Model for any kind of alert that can be associated with a bug."""

from google.appengine.ext import ndb

from dashboard.common import utils
from dashboard.models import internal_only_model
from dashboard.models import sheriff as sheriff_module


class Alert(internal_only_model.InternalOnlyModel):
  """General base class for alerts."""

  # Whether the alert should only be viewable by internal users.
  internal_only = ndb.BooleanProperty(indexed=True, default=False)

  # The time the alert fired.
  timestamp = ndb.DateTimeProperty(indexed=True, auto_now_add=True)

  # Note: -1 denotes an invalid alert and -2 an ignored alert.
  # By default, this is None, which denotes a non-triaged alert.
  bug_id = ndb.IntegerProperty(indexed=True)

  # The sheriff rotation that should handle this alert.
  sheriff = ndb.KeyProperty(kind=sheriff_module.Sheriff, indexed=True)

  # Each Alert is related to one Test.
  test = ndb.KeyProperty(indexed=True)

  # We'd like to be able to query Alerts by Master, Bot, and Benchmark names.
  master_name = ndb.ComputedProperty(
      lambda self: utils.TestPath(self.test).split('/')[0],
      indexed=True)
  bot_name = ndb.ComputedProperty(
      lambda self: utils.TestPath(self.test).split('/')[1],
      indexed=True)
  benchmark_name = ndb.ComputedProperty(
      lambda self: utils.TestPath(self.test).split('/')[2],
      indexed=True)

  # Each Alert has a revision range it's associated with; however,
  # start_revision and end_revision could be the same.
  start_revision = ndb.IntegerProperty(indexed=True)
  end_revision = ndb.IntegerProperty(indexed=True)

  # The group this alert belongs to.
  # TODO(qyearsley): If the old AnomalyGroup entities can be removed and
  # all recent groups have the kind AlertGroup, then the optional argument
  # kind=alert_group.AlertGroup can be added.
  group = ndb.KeyProperty(indexed=True)

  # The revisions to use for display, if different than point id.
  display_start = ndb.IntegerProperty(indexed=False)
  display_end = ndb.IntegerProperty(indexed=False)

  # Ownership data, mapping e-mails to the benchmark's owners' emails and
  # component as the benchmark's Monorail component
  ownership = ndb.JsonProperty()

  def GetTestMetadataKey(self):
    """Get the key for the TestMetadata entity of this alert.

    We are in the process of converting from Test entities to TestMetadata.
    Until this is done, it's possible that an alert may store either Test
    or TestMetadata in the 'test' KeyProperty. This gets the TestMetadata key
    regardless of what's stored.
    """
    return utils.TestMetadataKey(self.test)

  @classmethod
  def GetAlertsForTest(cls, test_key, limit=None):
    return cls.query(cls.test.IN([
        utils.TestMetadataKey(test_key),
        utils.OldStyleTestKey(test_key)])).fetch(limit=limit)


def _GetTestSuiteFromKey(test_key):
  """Gets test suite from |test_key|, None if not found."""
  pairs = test_key.pairs()
  if len(pairs) < 3:
    return None
  return pairs[2][1]


def GetBotNamesFromAlerts(alerts):
  """Gets a set with the names of the bots related to some alerts."""
  # a.test is the key of a TestMetadata entity, and the TestPath is a path like
  # master_name/bot_name/test_suite_name/metric...
  return {utils.TestPath(a.test).split('/')[1] for a in alerts}
