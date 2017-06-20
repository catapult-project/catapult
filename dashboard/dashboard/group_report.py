# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for a set of alerts and their graphs."""

import json

from google.appengine.ext import ndb

from dashboard import alerts
from dashboard import chart_handler
from dashboard import update_test_suites
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import page_state
from dashboard.models import stoppage_alert

# This is the max number of alerts to query at once. This is used in cases
# when we may want to query more many more alerts than actually get displayed.
_QUERY_LIMIT = 2000

# Maximum number of alerts that we might want to try display in one table.
_DISPLAY_LIMIT = 500


class GroupReportHandler(chart_handler.ChartHandler):
  """Request handler for requests for group report page."""

  def get(self):
    """Renders the UI for the group report page."""
    self.RenderStaticHtml('group_report.html')

  def post(self):
    """Returns dynamic data for /group_report with some set of alerts.

    The set of alerts is determined by the sid, keys, bug ID, or revision given.

    Request parameters:
      keys: A comma-separated list of urlsafe Anomaly keys (optional).
      bug_id: A bug number on the Chromium issue tracker (optional).
      rev: A revision number (optional).
      sid: A hash of a group of keys from /short_uri (optional).

    Outputs:
      JSON for the /group_report page XHR request.
    """
    bug_id = self.request.get('bug_id')
    rev = self.request.get('rev')
    keys = self.request.get('keys')
    hash_code = self.request.get('sid')

    # sid takes precedence.
    if hash_code:
      state = ndb.Key(page_state.PageState, hash_code).get()
      if state:
        keys = json.loads(state.value)
    elif keys:
      keys = keys.split(',')

    try:
      alert_list = None
      if bug_id:
        alert_list, extra_columns = GetAlertsWithBugId(bug_id)
      elif keys:
        alert_list, extra_columns = GetAlertsForKeys(keys)
      elif rev:
        alert_list, extra_columns = GetAlertsAroundRevision(rev)
      else:
        # TODO(qyearsley): Instead of just showing an error here, show a form
        # where the user can input a bug ID or revision.
        raise request_handler.InvalidInputError('No anomalies specified.')

      anomaly_dicts = alerts.AnomalyDicts(
          [a for a in alert_list if a.key.kind() == 'Anomaly'])
      stoppage_alert_dicts = alerts.StoppageAlertDicts(
          [a for a in alert_list if a.key.kind() == 'StoppageAlert'])
      alert_dicts = anomaly_dicts + stoppage_alert_dicts

      values = {
          'alert_list': alert_dicts[:_DISPLAY_LIMIT],
          'extra_columns': extra_columns,
          'test_suites': update_test_suites.FetchCachedTestSuites(),
      }
      if bug_id:
        values['bug_id'] = bug_id
      if keys:
        values['selected_keys'] = keys
      self.GetDynamicVariables(values)

      self.response.out.write(json.dumps(values))
    except request_handler.InvalidInputError as error:
      self.response.out.write(json.dumps({'error': str(error)}))


def GetAlertsWithBugId(bug_id):
  """Get alerts for |bug_id|.

  Args:
    bug_id: A bug ID (as an int or string). Could be also be a pseudo-bug ID,
        such as -1 or -2 indicating invalid or ignored.

  Returns:
    tuple (alerts, extra_columns)
  """
  if not _IsInt(bug_id):
    raise request_handler.InvalidInputError('Invalid bug ID "%s".' % bug_id)
  bug_id = int(bug_id)
  anomaly_query = anomaly.Anomaly.query(
      anomaly.Anomaly.bug_id == bug_id)
  anomalies = anomaly_query.fetch(limit=_DISPLAY_LIMIT)
  stoppage_alert_query = stoppage_alert.StoppageAlert.query(
      stoppage_alert.StoppageAlert.bug_id == bug_id)
  stoppage_alerts = stoppage_alert_query.fetch(limit=_DISPLAY_LIMIT)
  # If there are any anomalies on the bug, use anomaly extra columns.
  extra_columns = None
  if len(anomalies) > 0:
    extra_columns = 'anomalies'
  elif len(stoppage_alerts) > 0:
    extra_columns = 'stoppage_alerts'
  return anomalies + stoppage_alerts, extra_columns


def GetAlertsAroundRevision(rev):
  """Gets the alerts whose revision range includes the given revision.

  Args:
    rev: A revision number, as a string.

  Returns:
    tuple (alerts, extra_columns)
  """
  if not _IsInt(rev):
    raise request_handler.InvalidInputError('Invalid rev "%s".' % rev)
  rev = int(rev)

  # We can't make a query that has two inequality filters on two different
  # properties (start_revision and end_revision). Therefore we first query
  # Anomaly entities based on one of these, then filter the resulting list.
  anomaly_query = anomaly.Anomaly.query(anomaly.Anomaly.end_revision >= rev)
  anomaly_query = anomaly_query.order(anomaly.Anomaly.end_revision)
  anomalies = anomaly_query.fetch(limit=_QUERY_LIMIT)
  anomalies = [a for a in anomalies if a.start_revision <= rev]
  stoppage_alert_query = stoppage_alert.StoppageAlert.query(
      stoppage_alert.StoppageAlert.end_revision == rev)
  stoppage_alerts = stoppage_alert_query.fetch(limit=_DISPLAY_LIMIT)
  # Always show anomalies extra_columns for alerts around revision.
  return anomalies + stoppage_alerts, 'anomalies'


def GetAlertsForKeys(keys):
  """Get alerts for |keys|.

  Query for anomalies with overlapping revision. The |keys|
  parameter for group_report is a comma-separated list of urlsafe strings
  for Keys for Anomaly entities. (Each key corresponds to an alert)

  Args:
    keys: Comma-separated list of urlsafe strings for Anomaly keys.

  Returns:
    tuple (alerts, extra_columns)
  """
  urlsafe_keys = keys

  try:
    keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys]
  # Errors that can be thrown here include ProtocolBufferDecodeError
  # in google.net.proto.ProtocolBuffer. We want to catch any errors here
  # because they're almost certainly urlsafe key decoding errors.
  except Exception:
    raise request_handler.InvalidInputError('Invalid Anomaly key given.')

  requested_anomalies = utils.GetMulti(keys)

  extra_columns = None
  for i, anomaly_entity in enumerate(requested_anomalies):
    if isinstance(anomaly_entity, anomaly.Anomaly):
      extra_columns = 'anomalies'
    elif (isinstance(anomaly_entity, stoppage_alert.StoppageAlert) and
          extra_columns is None):
      extra_columns = 'stoppage_alerts'
    if anomaly_entity is None:
      raise request_handler.InvalidInputError(
          'No Anomaly found for key %s.' % urlsafe_keys[i])

  if not requested_anomalies:
    raise request_handler.InvalidInputError('No anomalies found.')

  sheriff_key = requested_anomalies[0].sheriff
  min_range = utils.MinimumAlertRange(requested_anomalies)
  if min_range:
    query = anomaly.Anomaly.query(
        anomaly.Anomaly.sheriff == sheriff_key)
    query = query.order(-anomaly.Anomaly.timestamp)
    anomalies = query.fetch(limit=_QUERY_LIMIT)

    # Filter out anomalies that have been marked as invalid or ignore.
    # Include all anomalies with an overlapping revision range that have
    # been associated with a bug, or are not yet triaged.
    requested_anomalies_set = set([a.key for a in requested_anomalies])
    def _IsValidAlert(a):
      if a.key in requested_anomalies_set:
        return False
      return a.bug_id is None or a.bug_id > 0

    anomalies = [a for a in anomalies if _IsValidAlert(a)]
    anomalies = _GetOverlaps(anomalies, min_range[0], min_range[1])

    # Make sure alerts in specified param "keys" are included.
    # We actually only send the first _DISPLAY_LIMIT alerts to the UI, so we
    # need to include those keys at the start of the list.
    anomalies = requested_anomalies + anomalies
  else:
    anomalies = requested_anomalies
  return anomalies, extra_columns


def _IsInt(x):
  """Returns True if the input can be parsed as an int."""
  try:
    int(x)
    return True
  except ValueError:
    return False


def _GetOverlaps(anomalies, start, end):
  """Gets the minimum range for the list of anomalies.

  Args:
    anomalies: The list of anomalies.
    start: The start revision.
    end: The end revision.

  Returns:
    A list of anomalies.
  """
  return [a for a in anomalies
          if a.start_revision <= end and a.end_revision >= start]
