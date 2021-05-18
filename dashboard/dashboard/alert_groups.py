# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging

from dashboard.common import request_handler
from dashboard.models import alert_group
from dashboard.models import alert_group_workflow
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.api import taskqueue


def _ProcessAlertGroup(group_key):
  workflow = alert_group_workflow.AlertGroupWorkflow(group_key.get())
  logging.info('Processing group: %s', group_key.string_id())
  workflow.Process()


def _ProcessUngroupedAlerts():
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
    alert_group.AlertGroup(name='Ungrouped', group_type=reserved,
                           active=True).put()
    return
  ungrouped = ungrouped_list[0]
  ungrouped_anomalies = ndb.get_multi(ungrouped.anomalies)

  # Scan all ungrouped anomalies and create missing groups. This doesn't
  # mean their groups are not created so we still need to check if group
  # has been created. There are two cases:
  # 1. If multiple groups are related to an anomaly, maybe only part of
  # groups are not created.
  # 2. Groups may be created during the iteration.
  # Newly created groups won't be updated until next iteration.
  for anomaly_entity in ungrouped_anomalies:
    anomaly_entity.groups = [
        FindGroup(g) or g.put() for g in
        alert_group.AlertGroup.GenerateAllGroupsForAnomaly(anomaly_entity)
    ]
  logging.info('Persisting anomalies')
  ndb.put_multi(ungrouped_anomalies)


def ProcessAlertGroups():
  logging.info('Fetching alert groups.')
  groups = alert_group.AlertGroup.GetAll()
  logging.info('Found %s alert groups.', len(groups))
  for group in groups:
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


class AlertGroupsHandler(request_handler.RequestHandler):
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
  def get(self):
    logging.info('Queueing task for deferred processing.')
    # Do not retry failed tasks.
    deferred.defer(
        ProcessAlertGroups,
        _queue='update-alert-group-queue',
        _retry_options=taskqueue.TaskRetryOptions(task_retry_limit=0),
    )
    self.response.write('OK')
