# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for a set of alerts and their graphs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import http
import json
import logging
import six

from google.appengine.ext import ndb

from dashboard import alerts
from dashboard import chart_handler
from dashboard import short_uri
from dashboard import update_test_suites
from dashboard.common import cloud_metric
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import page_state
from dashboard.models import skia_helper
from dashboard.services import perf_issue_service_client

from flask import request, make_response

# This is the max number of alerts to query at once. This is used in cases
# when we may want to query more many more alerts than actually get displayed.
_QUERY_LIMIT = 5000


def GroupReportGet():
  return request_handler.RequestHandlerRenderStaticHtml('group_report.html')


@cloud_metric.APIMetric("chromeperf", "/group_report")
def GroupReportPost():
  """Returns dynamic data for /group_report with some set of alerts.

    The set of alerts is determined by the sid, keys, bug ID, AlertGroup ID,
    or revision given.

    Request parameters:
      keys: A comma-separated list of urlsafe Anomaly keys (optional).
      bug_id: A bug number on the Chromium issue tracker (optional).
      project_id: A project ID in Monorail (optional).
      rev: A revision number (optional).
      sid: A hash of a group of keys from /short_uri (optional).
      group_id: An AlertGroup ID (optional).

    Outputs:
      JSON for the /group_report page XHR request.
    """
  bug_id = request.values.get('bug_id')
  project_id = request.values.get('project_id', 'chromium') or 'chromium'
  rev = request.values.get('rev')
  keys = request.values.get('keys')
  hash_code = request.values.get('sid')
  group_id = request.values.get('group_id')

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
      try:
        alert_list, _, _ = anomaly.Anomaly.QueryAsync(
            bug_id=bug_id, project_id=project_id,
            limit=_QUERY_LIMIT).get_result()
      except ValueError as e:
        six.raise_from(
            request_handler.InvalidInputError('Invalid bug ID "%s:%s".' %
                                              (project_id, bug_id)), e)
    elif keys:
      alert_list = GetAlertsForKeys(keys)
    elif rev:
      alert_list = GetAlertsAroundRevision(rev)
    elif group_id:
      alert_list = GetAlertsForGroupID(group_id)
    else:
      raise request_handler.InvalidInputError('No anomalies specified.')

    alert_dicts = alerts.AnomalyDicts([
        a for a in alert_list
        if a.key.kind() == 'Anomaly' and a.source != 'skia'
    ])

    values = {
        'alert_list': alert_dicts,
        'test_suites': update_test_suites.FetchCachedTestSuites(),
    }
    if bug_id:
      values['bug_id'] = bug_id
      values['project_id'] = project_id
    if keys:
      values['selected_keys'] = keys
    chart_handler.GetDynamicVariables(values)

    return make_response(json.dumps(values))
  except request_handler.InvalidInputError as error:
    return make_response(json.dumps({'error': str(error)}))


def SkiaPostAlertsByIntegerKeys():
  try:
    data = json.loads(request.data)
  except json.JSONDecodeError as e:
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by keys request from Skia: %s', data)

  keys = data.get('keys', '')
  if not keys:
    return make_response(
        json.dumps({'error': 'No key is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)
  try:
    # Try converting to validate keys before converting to sid.
    _ = [ndb.Key('Anomaly', int(k)) for k in keys.split(',')]
  except Exception as e:  # pylint: disable=broad-except
    return make_response(
        json.dumps({'error': 'Invalid Anomaly key given.'}),
        http.HTTPStatus.BAD_REQUEST.value)
  sid = short_uri.GetOrCreatePageState(keys)

  # The current POST call from does not need the alert list.
  return MakeResponseForSkiaAlerts([], data.get('host', ''), sid)


def ListSkiaAlertsByRev(rev):
  alert_list = []
  if not rev:
    return make_response(
        json.dumps({'error': 'No rev is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by revision request from Skia: %s',
      rev)

  try:
    alert_list = GetAlertsAroundRevision(rev)
  except request_handler.InvalidInputError as e:
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)
  return MakeResponseForSkiaAlerts(alert_list, request.values.get('host'))


def ListSkiaAlertsByGroupId(group_id):
  alert_list = []
  if not group_id:
    return make_response(
        json.dumps({'error': 'No group_id is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by group id request from Skia: %s',
      group_id)

  try:
    alert_list = GetAlertsForGroupID(group_id)
    logging.debug('[SkiaTriage] %d anomalies retrieved by group id %s',
                  len(alert_list), group_id)
  except request_handler.InvalidInputError as e:
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)

  return MakeResponseForSkiaAlerts(alert_list, request.values.get('host'))


def SkiaGetAlertsBySid():
  alert_list = []
  sid = request.values.get('sid')
  if not sid:
    return make_response(
        json.dumps({'error': 'No sid is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by sid request from Skia: %s', sid)

  state = ndb.Key(page_state.PageState, sid).get()
  if not state:
    return make_response(
        json.dumps({'error': 'No state is found from the sid %s.' % sid}),
        http.HTTPStatus.BAD_REQUEST.value)

  keys = state.value.decode("utf-8")
  keys_list = []
  try:
    keys_list = keys.split(',')
    alert_list = GetAlertsForKeys(keys_list, is_urlsafe=False)
  except Exception as e:  # pylint: disable=broad-except
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)

  return MakeResponseForSkiaAlerts(
      alert_list, request.values.get('host'), selected_keys=keys_list)


def SkiaGetAlertsByIntegerKey():
  alert_list = []
  key = request.values.get('key')
  if not key:
    return make_response(
        json.dumps({'error': 'No key is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by key request from Skia: %s', key)

  try:
    alert_list = GetAlertsForKeys([key], is_urlsafe=False)
  except Exception as e:  # pylint: disable=broad-except
    return make_response(
        json.dumps({'error': str(e)}), http.HTTPStatus.BAD_REQUEST.value)

  return MakeResponseForSkiaAlerts(
      alert_list, request.values.get('host'), selected_keys=[key])


def SkiaGetAlertsByBugId():
  alert_list = []
  bug_id = request.values.get('bug_id')
  if not bug_id:
    return make_response(
        json.dumps({'error': 'No bug id is found from the request.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  logging.debug(
      '[SkiaTriage] Received get anomalies by bug id request from Skia: %s',
      bug_id)

  try:
    alert_list, _, _ = anomaly.Anomaly.QueryAsync(
        bug_id=bug_id, limit=_QUERY_LIMIT).get_result()
  except ValueError as e:
    return make_response(
        json.dumps({'error': 'Invalid bug ID "%s". %s' % (bug_id, str(e))}),
        http.HTTPStatus.BAD_REQUEST.value)

  return MakeResponseForSkiaAlerts(alert_list, request.values.get('host'))


def MakeResponseForSkiaAlerts(alert_list, host, sid=None, selected_keys=None):
  """Make response for the anomaly list request specifically from Skia.

  Args:
    alert_list: a list of anomaly IDs in string
    host: the Skia instance name, which is used to get the master names it
          is correlated to, and whether it is an internal instance. Those
          values will be used to filter the anomalies before returning to
          Skia.
    sid: the page state id used to represent a list of anomaly keys.
    selected_keys: the keys from the original request, which will be used
          to tell which anomalies should be checked in the report page.

  Returns:
    A response in json format:
    {
      'anomaly_list': the list of anomalies to return
      'sid':          the state id.
      'selected_keys': the keys of the anomalies which should be checked.
      'error':        error message if any.
    }
  """
  if not host:
    return make_response(
        json.dumps(
            {'error': 'Host value is missing to load anomalies to Skia.'}),
        http.HTTPStatus.BAD_REQUEST.value)

  masters, is_internal = skia_helper.GetMastersAndIsInternalForHost(host)
  # If the request is from a internal instance, no filtering is needed;
  # otherwise, show external only.
  if not is_internal:
    alert_list = [a for a in alert_list if a.internal_only != True]
  if masters:
    alert_list = [a for a in alert_list if a.master_name in masters]

  values = {
      'anomaly_list': alerts.AnomalyDicts(alert_list, skia=True),
  }
  if sid:
    values['sid'] = sid
  if selected_keys:
    values['selected_keys'] = selected_keys

  return make_response(json.dumps(values))


def GetAlertsAroundRevision(rev):
  """Gets the alerts whose revision range includes the given revision.

  Args:
    rev: A revision number, as a string.

  Returns:
    list of anomaly.Anomaly
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
  return [a for a in anomalies if a.start_revision <= rev]


def GetAlertsForKeys(keys, is_urlsafe=True):
  """Get alerts for |keys|.

  Query for anomalies with overlapping revision. The |keys|
  parameter for group_report is a comma-separated list of urlsafe strings
  for Keys for Anomaly entities. (Each key corresponds to an alert)

  Args:
    keys: Comma-separated list of urlsafe strings for Anomaly keys.

  Returns:
    list of anomaly.Anomaly
  """
  original_keys = keys
  try:
    if is_urlsafe:
      keys = [ndb.Key(urlsafe=k) for k in original_keys]
    else:
      keys = [ndb.Key('Anomaly', int(k)) for k in original_keys]
  # Errors that can be thrown here include ProtocolBufferDecodeError
  # in google.net.proto.ProtocolBuffer. We want to catch any errors here
  # because they're almost certainly urlsafe key decoding errors.
  except Exception as e:  # pylint: disable=broad-except
    six.raise_from(
        request_handler.InvalidInputError('Invalid Anomaly key given.'), e)

  requested_anomalies = utils.GetMulti(keys)

  for i, anomaly_entity in enumerate(requested_anomalies):
    if anomaly_entity is None:
      raise request_handler.InvalidInputError('No Anomaly found for key %s.' %
                                              original_keys[i])

  if not requested_anomalies:
    raise request_handler.InvalidInputError('No anomalies found.')

  # Just an optimization because we can't fetch anomalies directly based
  # on revisions. Apply some filters to reduce unrelated anomalies.
  subscriptions = []
  for anomaly_entity in requested_anomalies:
    subscriptions.extend(anomaly_entity.subscription_names)
  subscriptions = list(set(subscriptions))
  min_range = utils.MinimumAlertRange(requested_anomalies)
  if min_range:
    anomalies, _, _ = anomaly.Anomaly.QueryAsync(
        subscriptions=subscriptions, limit=_QUERY_LIMIT).get_result()

    # Filter out anomalies that have been marked as invalid or ignore.
    # Include all anomalies with an overlapping revision range that have
    # been associated with a bug, or are not yet triaged.
    requested_anomalies_set = {a.key for a in requested_anomalies}

    def _IsValidAlert(a):
      if a.key in requested_anomalies_set:
        return False
      # The edit_anomalies request may set the bug_id to 0, which is equivalent
      # to setting the bug_id to None in Chromeperf. Here we only want to
      # filter out those with value -1 or -2.
      return a.bug_id is None or a.bug_id >= 0

    anomalies = [a for a in anomalies if _IsValidAlert(a)]
    anomalies = _GetOverlaps(anomalies, min_range[0], min_range[1])
    anomalies = requested_anomalies + anomalies
  else:
    anomalies = requested_anomalies
  return anomalies


def GetAlertsForGroupID(group_id):
  """Get alerts for AlertGroup.

  Args:
    group_id: AlertGroup ID

  Returns:
    list of anomaly.Anomaly
  """
  group = alert_group.AlertGroup.GetByID(group_id)
  if not group:
    raise request_handler.InvalidInputError('Invalid AlertGroup ID "%s".' %
                                            group_id)
  anomalies = perf_issue_service_client.GetAnomaliesByAlertGroupID(group_id)
  anomaly_keys = [
      ndb.Key('Anomaly', a) for a in anomalies if isinstance(a, int)
  ]
  if sorted(anomaly_keys) != sorted(group.anomalies):
    logging.warning('Imparity found for GetAnomaliesByAlertGroupID. %s, %s',
                    group.anomalies, anomaly_keys)
    cloud_metric.PublishPerfIssueServiceGroupingImpariry(
        'GetAnomaliesByAlertGroupID')
  return ndb.get_multi(anomaly_keys)


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
  return [
      a for a in anomalies
      if a.start_revision <= end and a.end_revision >= start
  ]
