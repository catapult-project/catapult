# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A base Model for any kind of alert that can be associated with a bug."""

from google.appengine.ext import ndb

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

  # Each Alert has a revision range it's associated with; however,
  # start_revision and end_revision could be the same.
  start_revision = ndb.IntegerProperty(indexed=True)
  end_revision = ndb.IntegerProperty(indexed=True)

  # The group this alert belongs to.
  # TODO(qyearsley): If the old AnomalyGroup entities can be removed and
  # all recent groups have the kind AlertGroup, then the optional argument
  # kind=alert_group.AlertGroup can be added.
  group = ndb.KeyProperty(indexed=True)

  def _pre_put_hook(self):
    """Updates the alert's group."""
    # TODO(qyearsley): Extract sub-methods from this method in order
    # to make it shorter.

    # The group should not be updated if this is the first time that the
    # the Alert is being put. (If the key is auto-assigned, then key.id()
    # will be None the first time.)
    if not self.key.id():
      return

    # The previous state of this alert. (If this is the first time the
    # alert is being put, then this will be None.
    original_alert = self.key.get(use_cache=False)
    if original_alert is None:
      return

    # If the alert does not have a group, don't do anything.
    if not self.group:
      return
    # If the group key is "AnomalyGroup" (the previous incarnation of
    # AlertGroup), we can just leave it as is. This will only apply to
    # already-existing Anomaly entities, not new Anomaly entities.
    if self.group.kind() != 'AlertGroup':
      self.group = None
      return
    group = self.group.get()
    if not group:
      return

    # Each AlertGroup should only be associated with entities of one class;
    # i.e. an Anomaly entity shouldn't be grouped with a StoppageAlert entity.
    alert_class = self.__class__

    # When the bug ID changes, this alert may be updated to belong
    # to the new group.
    if self.bug_id != original_alert.bug_id:
      grouped_alerts = alert_class.query(
          alert_class.group == group.key).fetch()
      grouped_alerts.append(self)

      # The alert has been assigned a real bug ID.
      # Update the group bug ID if necessary.
      if self.bug_id > 0 and group.bug_id != self.bug_id:
        group.bug_id = self.bug_id
        group.put()

      # The bug has been marked invalid/ignored. Kick it out of the group.
      elif self.bug_id < 0 and self.bug_id is not None:
        self._RemoveFromGroup(grouped_alerts)
        grouped_alerts.remove(self)

      # The bug has been un-triaged. Update the group's bug ID if this is
      # the only alert in the group.
      elif self.bug_id is None and len(grouped_alerts) == 1:
        group.bug_id = None
        group.put()

      # Check and update the group's revision range if necessary.
      group.UpdateRevisionRange(grouped_alerts)

    elif (self.end_revision != original_alert.end_revision or
          self.start_revision != original_alert.start_revision):
      grouped_alerts = alert_class.query(alert_class.group == group.key).fetch()
      grouped_alerts.append(self)
      group.UpdateRevisionRange(grouped_alerts)

  def _RemoveFromGroup(self, grouped_alerts):
    """Removes an alert from its group and updates the group's properties.

    Args:
      grouped_alerts: The list of alerts in |group| used to calculate
          new revision range; none are modified.
    """
    group = self.group.get()
    self.group = None
    grouped_alerts.remove(self)
    if not grouped_alerts:
      group.key.delete()
      return
    # Update minimum revision range for group.
    group.UpdateRevisionRange(grouped_alerts)


def _GetTestSuiteFromKey(test_key):
  """Gets test suite from |test_key|, None if not found."""
  pairs = test_key.pairs()
  if len(pairs) < 3:
    return None
  return pairs[2][1]


def GetBotNamesFromAlerts(alerts):
  """Gets a set with the names of the bots related to some alerts."""
  # a.test is a ndb.Key object, and a.test.flat() should return a list like
  # ['Master', master name, 'Bot', bot name, 'Test', test suite name, ...]
  return {a.test.flat()[3] for a in alerts}
