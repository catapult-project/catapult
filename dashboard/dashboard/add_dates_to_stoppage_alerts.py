# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue
from google.appengine.datastore import datastore_query
from google.appengine.ext import ndb

from dashboard.common import datastore_hooks
from dashboard.common import request_handler
from dashboard.models import stoppage_alert

_STOPPAGE_ALERTS_TO_PUT_AT_ONCE = 50

# Queue name needs to be listed in queue.yaml.
_TASK_QUEUE_NAME = 'task-runner-queue'


class AddDatesToStoppageAlertsHandler(request_handler.RequestHandler):
  """Adds last_row_timestamp to StopageAlerts."""

  def get(self):
    self.post()

  def post(self):
    """Queries for a page of stoppage alerts to set the last_row_timestamp."""
    datastore_hooks.SetPrivilegedRequest()

    query = stoppage_alert.StoppageAlert.query(
        stoppage_alert.StoppageAlert.bug_id == None)

    cursor = datastore_query.Cursor(urlsafe=self.request.get('cursor'))
    stoppage_alerts, next_cursor, more = query.fetch_page(
        _STOPPAGE_ALERTS_TO_PUT_AT_ONCE, start_cursor=cursor)

    for alert in stoppage_alerts:
      alert.last_row_timestamp = alert.last_row_date

    ndb.put_multi(stoppage_alerts)
    if more:
      task_params = {
          'cursor': next_cursor.urlsafe(),
      }
      taskqueue.add(
          url='/add_dates_to_stoppage_alerts',
          params=task_params,
          queue_name=_TASK_QUEUE_NAME)
