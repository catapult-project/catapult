# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json

from google.appengine.ext import ndb

from dashboard.api import api_auth
from dashboard.common import request_handler
from dashboard.models import anomaly
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
      JSON data; see README.md.
    """
    try:
      alert_list = self._GetAlerts(*args)
      self.response.out.write(json.dumps(alert_list))
    except BadRequestError as e:
      self._WriteErrorMessage(e.message, 500)
    except api_auth.NotLoggedInError:
      self._WriteErrorMessage('User not authenticated', 403)
    except api_auth.OAuthError:
      self._WriteErrorMessage('User authentication error', 403)

  @api_auth.Authorize
  def _GetAlerts(self, *args):
    alert_list = None
    list_type = args[0]
    try:
      if list_type.startswith('bug_id'):
        bug_id = list_type.replace('bug_id/', '')
        alert_list = group_report.GetAlertsWithBugId(bug_id)
      elif list_type.startswith('keys'):
        keys = list_type.replace('keys/', '').split(',')
        alert_list = group_report.GetAlertsForKeys(keys)
      elif list_type.startswith('rev'):
        rev = list_type.replace('rev/', '')
        alert_list = group_report.GetAlertsAroundRevision(rev)
      elif list_type.startswith('history'):
        try:
          days = int(list_type.replace('history/', ''))
        except ValueError:
          days = 7
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        sheriff_name = self.request.get('sheriff', 'Chromium Perf Sheriff')
        sheriff_key = ndb.Key('Sheriff', sheriff_name)
        sheriff = sheriff_key.get()
        if not sheriff:
          raise BadRequestError('Invalid sheriff %s' % sheriff_name)
        include_improvements = bool(self.request.get('improvements'))
        query = anomaly.Anomaly.query(anomaly.Anomaly.sheriff == sheriff_key)
        query = query.filter(anomaly.Anomaly.timestamp > cutoff)
        if not include_improvements:
          query = query.filter(
              anomaly.Anomaly.is_improvement == False)

        query = query.order(-anomaly.Anomaly.timestamp)
        alert_list = query.fetch()
      else:
        raise BadRequestError('Invalid alert type %s' % list_type)
    except request_handler.InvalidInputError as e:
      raise BadRequestError(e.message)

    anomaly_dicts = alerts.AnomalyDicts(
        [a for a in alert_list if a.key.kind() == 'Anomaly'])

    response = {
        'anomalies': anomaly_dicts
    }

    return response

  def _WriteErrorMessage(self, message, status):
    self.ReportError(message, status=status)
    self.response.out.write(json.dumps({'error': message}))

