# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Model for a group of alerts."""

import logging

from google.appengine.ext import ndb

from dashboard import quick_logger
from dashboard.common import utils

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
    Returns:
      True if modified, False otherwise.
    """
    min_rev_range = utils.MinimumAlertRange(grouped_alerts)
    start, end = min_rev_range if min_rev_range else (None, None)
    if self.start_revision != start or self.end_revision != end:
      self.start_revision = start
      self.end_revision = end
      return True
    return False


def ModifyAlertsAndAssociatedGroups(alert_entities, **kwargs):
  """Modifies a list of alerts and their corresponding groups.

  There's some book-keeping that needs to be done when modifying an alert,
  specifically when modifying either the bug_id or it's revision range. These
  can potentially trigger modifications or even deletions of AlertGroups.

  Args:
    alert_entities: A list of alert entities to modify.
    bug_id: An optional bug_id to set.
    start_revision: An optional start_revision to set.
    end_revision: An optional end_revision to set.
  """
  modified_groups = {}
  modified_alerts = []
  deleted_groups = []

  valid_args = ['bug_id', 'start_revision', 'end_revision']

  # 1st pass, for each alert that's modified, kick off an async get for
  # it's group.
  group_futures = {}
  valid_alerts = []
  for a in alert_entities:
    if not a.group or a.group.kind() != 'AlertGroup':
      a.group = None

    modified = False

    # We use kwargs instead of default args since None is actually a valid
    # value to set and using kwargs let's us easily distinguish betwen
    # setting None, and not passing that arg at all.
    for v in valid_args:
      if v in kwargs:
        if getattr(a, v) != kwargs[v]:
          setattr(a, v, kwargs[v])
          modified = True

    if not modified:
      continue

    modified_alerts.append(a)

    if not a.group:
      continue

    if not a.group.id() in group_futures:
      group_futures[a.group.id()] = a.group.get_async()

    valid_alerts.append(a)

  # 2nd pass, for each group, kick off async queries for any other alerts in
  # the same group.
  alert_entities = valid_alerts
  valid_alerts = []
  grouped_alerts_futures = {}
  for a in alert_entities:
    group_future = group_futures[a.group.id()]
    group_entity = group_future.get_result()
    if not group_entity:
      continue

    valid_alerts.append(a)

    if a.group.id() in grouped_alerts_futures:
      continue

    alert_cls = a.__class__
    grouped_alerts_future = alert_cls.query(
        alert_cls.group == group_entity.key).fetch_async()
    grouped_alerts_futures[a.group.id()] = grouped_alerts_future

  # 3rd pass, modify groups
  alert_entities = valid_alerts
  grouped_alerts_cache = {}
  for a in alert_entities:
    # We cache these rather than grab get_result() each time because we may
    # modify them in a previous iteration and we want those modifications.
    if a.group.id() in grouped_alerts_cache:
      group_entity, grouped_alerts = grouped_alerts_cache[a.group.id()]
    else:
      group_entity = group_futures[a.group.id()].get_result()
      grouped_alerts = grouped_alerts_futures[a.group.id()].get_result()
      grouped_alerts_cache[a.group.id()] = (group_entity, grouped_alerts)

    if not a in grouped_alerts:
      grouped_alerts.append(a)

    if 'bug_id' in kwargs:
      bug_id = kwargs['bug_id']
      # The alert has been assigned a real bug ID.
      # Update the group bug ID if necessary.
      if bug_id > 0 and group_entity.bug_id != bug_id:
        group_entity.bug_id = bug_id
        modified_groups[group_entity.key.id()] = group_entity
      # The bug has been marked invalid/ignored. Kick it out of the group.
      elif bug_id < 0 and bug_id is not None:
        a.group = None
        grouped_alerts.remove(a)
      # The bug has been un-triaged. Update the group's bug ID if this is
      # the only alert in the group.
      elif bug_id is None and len(grouped_alerts) == 1:
        group_entity.bug_id = None
        modified_groups[group_entity.key.id()] = group_entity

    if group_entity.UpdateRevisionRange(grouped_alerts):
      modified_groups[group_entity.key.id()] = group_entity

  # Do final pass to remove all empty groups. If we both delete the group and
  # put() it back after modifications, it's a race as to which actually happens.
  for k, (group_entity, grouped_alerts) in grouped_alerts_cache.iteritems():
    if not grouped_alerts:
      deleted_groups.append(group_entity.key)
      if k in modified_groups:
        del modified_groups[k]

  modified_groups = modified_groups.values()

  futures = ndb.delete_multi_async(deleted_groups)
  futures.extend(ndb.put_multi_async(modified_alerts + modified_groups))

  ndb.Future.wait_all(futures)


@ndb.synctasklet
def GroupAlerts(alerts, test_suite, kind):
  """Groups alerts with matching criteria.

  Assigns a bug_id or a group_id if there is a matching group,
  otherwise creates a new group for that anomaly.

  Args:
    alerts: A list of Alerts.
    test_suite: The test suite name for |alerts|.
    kind: The kind string of the given alert entity.
  """
  yield GroupAlertsAsync(alerts, test_suite, kind)


@ndb.tasklet
def GroupAlertsAsync(alerts, test_suite, kind):
  if not alerts:
    return
  alerts = [a for a in alerts if not getattr(a, 'is_improvement', False)]
  alerts = sorted(alerts, key=lambda a: a.end_revision)
  if not alerts:
    return
  groups = yield _FetchAlertGroups(alerts[-1].end_revision)

  for alert_entity in alerts:
    matching_group = _FindMatchingAlertGroup(
        alert_entity, groups, test_suite, kind)

    if not matching_group:
      matching_group = yield _CreateGroupForAlert(
          alert_entity, test_suite, kind)
    else:
      if matching_group.bug_id:
        alert_entity.bug_id = matching_group.bug_id
        _AddLogForBugAssociate(alert_entity)
      logging.debug('Auto triage: Associated anomaly on %s with %s.',
                    utils.TestPath(alert_entity.GetTestMetadataKey()),
                    matching_group.key.urlsafe())

    alert_entity.group = matching_group.key

    if matching_group.UpdateRevisionRange([alert_entity, matching_group]):
      yield matching_group.put_async()


@ndb.tasklet
def _FetchAlertGroups(max_start_revision):
  """Fetches AlertGroup entities up to a given revision."""
  query = AlertGroup.query(AlertGroup.start_revision <= max_start_revision)
  query = query.order(-AlertGroup.start_revision)
  groups = yield query.fetch_async(limit=_MAX_GROUPS_TO_FETCH)

  raise ndb.Return(groups)


def _FindMatchingAlertGroup(alert_entity, groups, test_suite, kind):
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
    The group that matches the alert, otherwise None.
  """
  for group in groups:
    if (_IsOverlapping(alert_entity, group.start_revision, group.end_revision)
        and group.alert_kind == kind
        and test_suite in group.test_suites):
      return group
  return None


@ndb.tasklet
def _CreateGroupForAlert(alert_entity, test_suite, kind):
  """Creates an AlertGroup for |alert_entity|."""
  group = AlertGroup()
  group.start_revision = alert_entity.start_revision
  group.end_revision = alert_entity.end_revision
  group.test_suites = [test_suite]
  group.alert_kind = kind
  yield group.put_async()
  logging.debug('Auto triage: Created group %s.', group)
  raise ndb.Return(group)


def _IsOverlapping(alert_entity, start, end):
  """Whether |alert_entity| overlaps with |start| and |end| revision range."""
  return (alert_entity.start_revision <= end and
          alert_entity.end_revision >= start)


def _AddLogForBugAssociate(anomaly_entity):
  """Adds a log for associating alert with a bug."""
  bug_id = anomaly_entity.bug_id
  sheriff = anomaly_entity.GetTestMetadataKey().get().sheriff
  if not sheriff:
    return
  # TODO(qyearsley): Add test coverage. See catapult:#1346.
  sheriff = sheriff.string_id()
  bug_url = ('https://chromeperf.appspot.com/group_report?bug_id=' +
             str(bug_id))
  test_path = utils.TestPath(anomaly_entity.GetTestMetadataKey())
  html_str = ('Associated alert on %s with bug <a href="%s">%s</a>.' %
              (test_path, bug_url, bug_id))
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('auto_triage', sheriff, formatter)
  logger.Log(html_str)
  logger.Save()
