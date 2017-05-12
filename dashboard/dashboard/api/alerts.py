# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

from dashboard.api import oauth
from dashboard.common import request_handler
from dashboard import alerts
from dashboard import group_report


class BadRequestError(Exception):
  pass


class AlertsHandler(request_handler.RequestHandler):
  """API handler for various alert requests."""

  def post(self, *args):
    """Returns alert data in response to API requests.

    Possible list types:
      keys: A comma-separated list of urlsafe Anomaly keys.
      bug_id: A bug number on the Chromium issue tracker.
      rev: A revision number.

    Outputs:
      JSON data for an XHR request to show a table of alerts.
    """
    try:
      alert_list = self._GetAlerts(*args)
      self.response.out.write(json.dumps(alert_list))
    except BadRequestError as e:
      self._WriteErrorMessage(e.message, 500)
    except oauth.NotLoggedInError:
      self._WriteErrorMessage('User not authenticated', 403)
    except oauth.OAuthError:
      self._WriteErrorMessage('User authentication error', 403)

  @oauth.Authorize
  def _GetAlerts(self, *args):
    alert_list = None
    list_type = args[0]
    try:
      if list_type.startswith('bug_id'):
        bug_id = list_type.replace('bug_id/', '')
        alert_list, _ = group_report.GetAlertsWithBugId(bug_id)
      elif list_type.startswith('keys'):
        keys = list_type.replace('keys/', '').split(',')
        alert_list, _ = group_report.GetAlertsForKeys(keys)
      elif list_type.startswith('rev'):
        rev = list_type.replace('rev/', '')
        alert_list, _ = group_report.GetAlertsAroundRevision(rev)
      else:
        raise BadRequestError('Invalid alert type %s' % list_type)
    except request_handler.InvalidInputError as e:
      raise BadRequestError(e.message)

    anomaly_dicts = alerts.AnomalyDicts(
        [a for a in alert_list if a.key.kind() == 'Anomaly'])
    stoppage_alert_dicts = alerts.StoppageAlertDicts(
        [a for a in alert_list if a.key.kind() == 'StoppageAlert'])

    response = {}
    if anomaly_dicts:
      response['anomalies'] = anomaly_dicts
    if stoppage_alert_dicts:
      response['stoppage_alerts'] = stoppage_alert_dicts

    return response

  def _WriteErrorMessage(self, message, status):
    self.ReportError(message, status=status)
    self.response.out.write(json.dumps({'error': message}))

