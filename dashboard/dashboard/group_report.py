# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for a set of alerts and their graphs."""

import json

from google.appengine.ext import ndb

from dashboard import alerts
from dashboard import chart_handler
from dashboard import list_tests
from dashboard import request_handler
from dashboard import test_owner
from dashboard import update_test_suites
from dashboard import utils
from dashboard.models import anomaly
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

    The set of alerts is determined by the keys, bug ID or revision given.

    Request parameters:
      keys: A comma-separated list of urlsafe Anomaly keys (optional).
      bug_id: A bug number on the Chromium issue tracker (optional).
      rev: A revision number (optional).

    Outputs:
      JSON for the /group_report page XHR request.
    """
    keys = self.request.get('keys')
    bug_id = self.request.get('bug_id')
    rev = self.request.get('rev')

    try:
      if bug_id:
        self._ShowAlertsWithBugId(bug_id)
      elif keys:
        self._ShowAlertsForKeys(keys)
      elif rev:
        self._ShowAlertsAroundRevision(rev)
      else:
        # TODO(qyearsley): Instead of just showing an error here, show a form
        # where the user can input a bug ID or revision.
        raise request_handler.InvalidInputError('No anomalies specified.')
    except request_handler.InvalidInputError as error:
      self.response.out.write(json.dumps({'error': str(error)}))

  def _ShowAlertsWithBugId(self, bug_id):
    """Show alerts for |bug_id|.

    Args:
      bug_id: A bug ID (as an int or string). Could be also be a pseudo-bug ID,
          such as -1 or -2 indicating invalid or ignored.
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
    self._ShowAlerts(anomalies + stoppage_alerts, bug_id)

  def _ShowAlertsAroundRevision(self, rev):
    """Shows a alerts whose revision range includes the given revision.

    Args:
      rev: A revision number, as a string.
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
    self._ShowAlerts(anomalies + stoppage_alerts)

  def _ShowAlertsForKeys(self, keys):
    """Show alerts for |keys|.

    Query for anomalies with overlapping revision. The |keys|
    parameter for group_report is a comma-separated list of urlsafe strings
    for Keys for Anomaly entities. (Each key corresponds to an alert)

    Args:
      keys: Comma-separated list of urlsafe strings for Anomaly keys.
    """
    urlsafe_keys = keys.split(',')
    try:
      keys = [ndb.Key(urlsafe=k) for k in urlsafe_keys]
    # Errors that can be thrown here include ProtocolBufferDecodeError
    # in google.net.proto.ProtocolBuffer. We want to catch any errors here
    # because they're almost certainly urlsafe key decoding errors.
    except Exception:
      raise request_handler.InvalidInputError('Invalid Anomaly key given.')

    requested_anomalies = utils.GetMulti(keys)

    for i, anomaly_entity in enumerate(requested_anomalies):
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
      anomalies = [a for a in anomalies if a.bug_id is None or a.bug_id > 0]
      anomalies = _GetOverlaps(anomalies, min_range[0], min_range[1])

      # Make sure alerts in specified param "keys" are included.
      key_set = {a.key for a in anomalies}
      for anomaly_entity in requested_anomalies:
        if anomaly_entity.key not in key_set:
          anomalies.append(anomaly_entity)
    else:
      anomalies = requested_anomalies
    self._ShowAlerts(anomalies)

  def _ShowAlerts(self, alert_list, bug_id=None):
    """Responds to an XHR from /group_report page with a JSON list of alerts.

    Args:
      alert_list: A list of Anomaly and/or StoppageAlert entities.
      bug_id: An integer bug ID.
    """
    anomaly_dicts = alerts.AnomalyDicts(
        [a for a in alert_list if a.key.kind() == 'Anomaly'])
    stoppage_alert_dicts = alerts.StoppageAlertDicts(
        [a for a in alert_list if a.key.kind() == 'StoppageAlert'])
    alert_dicts = anomaly_dicts + stoppage_alert_dicts
    owner_info = None
    if bug_id and ndb.Key('Bug', bug_id).get():
      owner_info = _GetOwnerInfo(alert_dicts)

    values = {
        'alert_list': alert_dicts[:_DISPLAY_LIMIT],
        'subtests': _GetSubTestsForAlerts(alert_dicts),
        'bug_id': bug_id,
        'owner_info': owner_info,
        'test_suites': update_test_suites.FetchCachedTestSuites(),
    }
    self.GetDynamicVariables(values)

    self.response.out.write(json.dumps(values))


def _IsInt(x):
  """Returns True if the input can be parsed as an int."""
  try:
    int(x)
    return True
  except ValueError:
    return False


def _GetSubTestsForAlerts(alert_list):
  """Gets subtest dict for list of alerts."""
  subtests = {}
  for alert in alert_list:
    bot_name = alert['master'] + '/' + alert['bot']
    testsuite = alert['testsuite']
    if bot_name not in subtests:
      subtests[bot_name] = {}
    if testsuite not in subtests[bot_name]:
      subtests[bot_name][testsuite] = list_tests.GetSubTests(
          testsuite, [bot_name])
  return subtests


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


def _GetOwnerInfo(alert_dicts):
  """Gets a list of owner info for list of alerts for bug with bisect result.

  Test owners are retrieved by a set of master and test suite name from each
  alert in alert_dicts.

  Args:
    alert_dicts: List of alert data dictionaries.

  Returns:
    A list of dictionary containing owner information.
  """
  test_suite_paths = {'%s/%s' % (a['master'], a['testsuite'])
                      for a in alert_dicts}
  owners = test_owner.GetOwners(test_suite_paths)
  return [{'email': owner} for owner in owners]
