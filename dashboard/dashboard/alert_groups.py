# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from flask import make_response

from dashboard.common import cloud_metric
from dashboard.models import alert_group
from dashboard.models import alert_group_workflow
from dashboard.services import perf_issue_service_client
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.api import taskqueue


def _ProcessAlertGroup(group_key):
  workflow = alert_group_workflow.AlertGroupWorkflow(group_key.get())
  logging.info('Processing group: %s', group_key.string_id())
  workflow.Process()


def _ProcessUngroupedAlerts():
  ''' Process alerts which need a new group
  '''
  # Parity
  try:
    parity_results = perf_issue_service_client.PostUngroupedAlerts()
  except Exception as e:  # pylint: disable=broad-except
    logging.warning('Parity failed in calling PostUngroupedAlerts. %s', str(e))

  groups = alert_group.AlertGroup.GetAll()

  # TODO(fancl): This is an inefficient algorithm, as it's linear to the number
  # of groups. We should instead create an interval tree so that it's
  # logarithmic to the number of unique revision ranges.
  def FindGroup(group):
    for g in groups:
      if group.IsOverlapping(g):
        return g.key
    groups.append(group)
    return None

  logging.info('Processing un-grouped alerts.')
  reserved = alert_group.AlertGroup.Type.reserved
  ungrouped_list = alert_group.AlertGroup.Get('Ungrouped', reserved)
  if not ungrouped_list:
    alert_group.AlertGroup(
        name='Ungrouped', group_type=reserved, active=True).put()
    return

  ungrouped = ungrouped_list[0]
  ungrouped_anomalies = ndb.get_multi(ungrouped.anomalies)

  # Parity on anomaly counts under ungrouped
  try:
    ungrouped_anomaly_keys = [
        str(a.key.integer_id()) for a in ungrouped_anomalies
    ]
    new_ungrouped_anomaly_keys = [str(k) for k in list(parity_results.keys())]
    if sorted(ungrouped_anomaly_keys) != sorted(new_ungrouped_anomaly_keys):
      logging.warning(
          'Imparity found for PostUngroupedAlerts - anomaly count. %s, %s',
          ungrouped_anomaly_keys, new_ungrouped_anomaly_keys)
      cloud_metric.PublishPerfIssueServiceGroupingImpariry(
          'PostUngroupedAlerts')
  except Exception as e:  # pylint: disable=broad-except
    logging.warning('Parity failed in PostUngroupedAlerts - anomaly count. %s',
                    str(e))

  # Scan all ungrouped anomalies and create missing groups. This doesn't
  # mean their groups are not created so we still need to check if group
  # has been created. There are two cases:
  # 1. If multiple groups are related to an anomaly, maybe only part of
  # groups are not created.
  # 2. Groups may be created during the iteration.
  # Newly created groups won't be updated until next iteration.
  for anomaly_entity in ungrouped_anomalies:
    new_count = 0
    alert_groups = []
    all_groups = alert_group.AlertGroup.GenerateAllGroupsForAnomaly(
        anomaly_entity)
    for g in all_groups:
      found_group = FindGroup(g)
      if found_group:
        alert_groups.append(found_group)
      else:
        new_group = g.key
        alert_groups.append(new_group)
        new_count += 1
    anomaly_entity.groups = alert_groups

    # parity on changes on group changes on anomalies
    try:
      single_parity = parity_results.get(anomaly_entity.key.integer_id(), None)
      if single_parity:
        existings = single_parity['existing_groups']
        news = single_parity['new_groups']
        if new_count != len(news):
          logging.warning(
              'Imparity found for PostUngroupedAlerts - new groups. %s, %s',
              new_count, len(news))
          cloud_metric.PublishPerfIssueServiceGroupingImpariry(
              'PostUngroupedAlerts - new groups')
        group_keys = [group.key.string_id() for group in groups]
        for g in existings:
          if g not in group_keys:
            logging.warning(
                'Imparity found for PostUngroupedAlerts - old groups. %s, %s',
                existings, group_keys)
            cloud_metric.PublishPerfIssueServiceGroupingImpariry(
                'PostUngroupedAlerts - old groups')
    except Exception as e:  # pylint: disable=broad-except
      logging.warning(
          'Parity failed in PostUngroupedAlerts - group match on %s. %s',
          anomaly_entity.key, str(e))


def ProcessAlertGroups():
  logging.info('Fetching alert groups.')
  groups = alert_group.AlertGroup.GetAll()
  logging.info('Found %s alert groups.', len(groups))
  # Parity on get all
  try:
    group_keys = perf_issue_service_client.GetAllActiveAlertGroups()
    logging.info('Parity found %s alert groups.', len(group_keys))
    original_group_keys = [str(g.key.id()) for g in groups]
    parity_keys = list(map(str, group_keys))
    new_groups = ndb.get_multi([ndb.Key('AlertGroup', k) for k in group_keys])
    if sorted(parity_keys) != sorted(original_group_keys):
      logging.warning('Imparity found for GetAllActiveAlertGroups. %s, %s',
                      group_keys, original_group_keys)
      cloud_metric.PublishPerfIssueServiceGroupingImpariry(
          'GetAllActiveAlertGroups')
  except Exception as e:  # pylint: disable=broad-except
    logging.warning('Parity logic failed in GetAllActiveAlertGroups. %s',
                    str(e))

  for group in new_groups:
    deferred.defer(
        _ProcessAlertGroup,
        group.key,
        _queue='update-alert-group-queue',
        _retry_options=taskqueue.TaskRetryOptions(task_retry_limit=0),
    )

  deferred.defer(
      _ProcessUngroupedAlerts,
      _queue='update-alert-group-queue',
      _retry_options=taskqueue.TaskRetryOptions(task_retry_limit=0),
  )


@cloud_metric.APIMetric("chromeperf", "/alert_groups_update")
def AlertGroupsGet():
  """Create and Update AlertGroups.

  All active groups are fetched and updated in every iteration. Auto-Triage
  and Auto-Bisection are triggered based on configuration in matching
  subscriptions.

  If an anomaly is associated with a special group named Ungrouped, all
  missing groups related to this anomaly will be created. Newly created groups
  won't be updated until next iteration.

  Groups will be archived after a time window passes and in status:
  - Untriaged: Only improvements in the group or auto-triage not enabled.
  - Closed: Issue closed.
  """
  logging.info('Queueing task for deferred processing.')
  # Do not retry failed tasks.
  deferred.defer(
      ProcessAlertGroups,
      _queue='update-alert-group-queue',
      _retry_options=taskqueue.TaskRetryOptions(task_retry_limit=0),
  )
  return make_response('OK')
