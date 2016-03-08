# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model for a group of alerts."""

import logging

from google.appengine.ext import ndb

from dashboard import quick_logger
from dashboard import utils

# Max number of AlertGroup entities to fetch.
_MAX_GROUPS_TO_FETCH = 2000


class AlertGroup(ndb.Model):
  """Represents a group of alerts that are likely to have the same cause."""

  # Issue tracker id.
  bug_id = ndb.IntegerProperty(indexed=True)

  # The minimum start of the revision range where the anomaly occurred.
  start_revision = ndb.IntegerProperty(indexed=True)

  # The minimum end of the revision range where the anomaly occurred.
  end_revision = ndb.IntegerProperty(indexed=False)

  # A list of test suites.
  test_suites = ndb.StringProperty(repeated=True, indexed=False)

  # The kind of the alerts in this group. Each group only has one kind.
  alert_kind = ndb.StringProperty(indexed=False)

  def UpdateRevisionRange(self, grouped_alerts):
    """Sets this group's revision range the minimum of the given group.

    Args:
      grouped_alerts: Alert entities that belong to this group. These
          are only given here so that they don't need to be fetched.
    """
    min_rev_range = utils.MinimumAlertRange(grouped_alerts)
    start, end = min_rev_range if min_rev_range else (None, None)
    if self.start_revision != start or self.end_revision != end:
      self.start_revision = start
      self.end_revision = end
      self.put()


def GroupAlerts(alerts, test_suite, kind):
  """Groups alerts with matching criteria.

  Assigns a bug_id or a group_id if there is a matching group,
  otherwise creates a new group for that anomaly.

  Args:
    alerts: A list of Alerts.
    test_suite: The test suite name for |alerts|.
    kind: The kind string of the given alert entity.
  """
  if not alerts:
    return
  alerts = [a for a in alerts if not getattr(a, 'is_improvement', False)]
  alerts = sorted(alerts, key=lambda a: a.end_revision)
  if not alerts:
    return
  groups = _FetchAlertGroups(alerts[-1].end_revision)
  for alert_entity in alerts:
    if not _FindAlertGroup(alert_entity, groups, test_suite, kind):
      _CreateGroupForAlert(alert_entity, test_suite, kind)


def _FetchAlertGroups(max_start_revision):
  """Fetches AlertGroup entities up to a given revision."""
  query = AlertGroup.query(AlertGroup.start_revision <= max_start_revision)
  query = query.order(-AlertGroup.start_revision)
  groups = query.fetch(limit=_MAX_GROUPS_TO_FETCH)

  return groups


def _FindAlertGroup(alert_entity, groups, test_suite, kind):
  """Finds and assigns a group for |alert_entity|.

  An alert should only be assigned an existing group if the group if
  the other alerts in the group are of the same kind, which should be
  the case if the alert_kind property of the group matches the alert's
  kind.

  Args:
    alert_entity: Alert to find group for.
    groups: List of AlertGroup.
    test_suite: The test suite of |alert_entity|.
    kind: The kind string of the given alert entity.

  Returns:
    True if a group is found and assigned, False otherwise.
  """
  for group in groups:
    if (_IsOverlapping(alert_entity, group.start_revision, group.end_revision)
        and group.alert_kind == kind
        and test_suite in group.test_suites):
      _AddAlertToGroup(alert_entity, group)
      return True
  return False


def _CreateGroupForAlert(alert_entity, test_suite, kind):
  """Creates an AlertGroup for |alert_entity|."""
  group = AlertGroup()
  group.start_revision = alert_entity.start_revision
  group.end_revision = alert_entity.end_revision
  group.test_suites = [test_suite]
  group.alert_kind = kind
  group.put()
  alert_entity.group = group.key
  logging.debug('Auto triage: Created group %s.', group)


def _AddAlertToGroup(alert_entity, group):
  """Adds an anomaly to group and updates the group's properties."""
  update_group = False
  if alert_entity.start_revision > group.start_revision:
    # TODO(qyearsley): Add test coverage. See catapult:#1346.
    group.start_revision = alert_entity.start_revision
    update_group = True
  if alert_entity.end_revision < group.end_revision:
    group.end_revision = alert_entity.end_revision
    update_group = True
  if update_group:
    group.put()

  if group.bug_id:
    alert_entity.bug_id = group.bug_id
    _AddLogForBugAssociate(alert_entity, group.bug_id)
  alert_entity.group = group.key
  logging.debug('Auto triage: Associated anomaly on %s with %s.',
                utils.TestPath(alert_entity.test),
                group.key.urlsafe())


def _IsOverlapping(alert_entity, start, end):
  """Whether |alert_entity| overlaps with |start| and |end| revision range."""
  return (alert_entity.start_revision <= end and
          alert_entity.end_revision >= start)


def _AddLogForBugAssociate(anomaly_entity, bug_id):
  """Adds a log for associating alert with a bug."""
  sheriff = anomaly_entity.test.get().sheriff
  if not sheriff:
    return
  # TODO(qyearsley): Add test coverage. See catapult:#1346.
  sheriff = sheriff.string_id()
  bug_url = ('https://chromeperf.appspot.com/group_report?bug_id=' +
             str(bug_id))
  test_path = utils.TestPath(anomaly_entity.test)
  html_str = ('Associated alert on %s with bug <a href="%s">%s</a>.' %
              (test_path, bug_url, bug_id))
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('auto_triage', sheriff, formatter)
  logger.Log(html_str)
  logger.Save()
