# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to automatically triage alerts.

This cron job manages alerts and issue tracker bugs.
"""

import datetime
import logging

from google.appengine.api import app_identity
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from dashboard import datastore_hooks
from dashboard import find_anomalies
from dashboard import issue_tracker_service
from dashboard import math_utils
from dashboard import quick_logger
from dashboard import request_handler
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import bug_data
from dashboard.models import sheriff

_TASK_QUEUE_NAME = 'auto-triage-queue'

# This is the max queried untriaged anomalies per sheriff.
# Takes about 30 seconds to fetch 2000 anomalies per sheriff.
_MAX_UNTRIAGED_ANOMALIES = 2000

# Number of days to query for bugs.
_OLDEST_BUG_DELTA = datetime.timedelta(days=30)

# Maximum relative difference between two steps for them to be considered
# similar enough for the second to be a "recovery" of the first.
# For example, if there's an increase of 5 units followed by a decrease of 6
# units, the relative difference of the deltas is 0.2.
_MAX_DELTA_DIFFERENCE = 0.25


class AutoTriageHandler(request_handler.RequestHandler):
  """URL endpoint for a cron job to automatically triage anomalies and bugs."""

  def get(self):
    """A get request is the same a post request for this endpoint."""
    self.post()

  def post(self):
    """Performs any automatic triaging operations.

    This will include updating Anomaly entities, and checking whether they
    should be marked as "recovered", as well as updating Bug entities, and
    commenting on the issue tracker if all alerts for a bug are recovered.
    """
    datastore_hooks.SetPrivilegedRequest()

    # Handle task queue requests.
    if self.request.get('update_recovered_bug'):
      bug_id = int(self.request.get('bug_id'))
      TriageBugs.UpdateRecoveredBugs(bug_id)
      return

    logging.info('Triaging anomalies')
    TriageAnomalies.Process()
    utils.TickMonitoringCustomMetric('TriageAnomalies')
    logging.info('Triaging bugs')
    TriageBugs.Process()
    utils.TickMonitoringCustomMetric('TriageBugs')
    logging.info('/auto_triage complete')


class TriageAnomalies(object):
  """Class for triaging anomalies."""

  @classmethod
  def Process(cls):
    """Processes anomalies."""
    # Check for recovered anomalies that are untriaged.
    anomalies = cls._FetchUntriagedAnomalies()
    recovered_anomalies = _FindAndUpdateRecoveredAnomalies(anomalies)
    map(_AddLogForRecoveredAnomaly, recovered_anomalies)

  @classmethod
  def _FetchUntriagedAnomalies(cls):
    """Fetches recent untriaged anomalies asynchronously from all sheriffs."""
    anomalies = []
    futures = []
    sheriff_keys = sheriff.Sheriff.query().fetch(keys_only=True)

    for key in sheriff_keys:
      query = anomaly.Anomaly.query(
          anomaly.Anomaly.sheriff == key,
          anomaly.Anomaly.bug_id == None,
          anomaly.Anomaly.is_improvement == False,
          anomaly.Anomaly.recovered == False)
      query = query.order(-anomaly.Anomaly.timestamp)
      futures.append(query.fetch_async(limit=_MAX_UNTRIAGED_ANOMALIES))
    ndb.Future.wait_all(futures)
    for future in futures:
      anomalies.extend(future.get_result())
    return anomalies


class TriageBugs(object):
  """Class for triaging bugs."""

  @classmethod
  def Process(cls):
    """Processes bugs."""
    bugs = cls._FetchLatestBugs()

    # For each bugs, add a task to check if all their anomalies have recovered.
    for bug in bugs:
      logging.info('Processing bug %s', bug.key.id())
      if bug.status == bug_data.BUG_STATUS_OPENED:
        logging.info('Adding update task to task queue')
        taskqueue.add(
            url='/auto_triage',
            params={'update_recovered_bug': True, 'bug_id': bug.key.id()},
            queue_name=_TASK_QUEUE_NAME)

  @classmethod
  def UpdateRecoveredBugs(cls, bug_id):
    """Checks whether Anomalies with a given bug ID have recovered."""
    anomalies = anomaly.Anomaly.query(
        anomaly.Anomaly.bug_id == bug_id).fetch()
    # If no anomalies found, mark this Bug entity as closed.
    if not anomalies:
      bug = ndb.Key('Bug', bug_id).get()
      bug.status = bug_data.BUG_STATUS_CLOSED
      bug.put()
      return

    non_recovered_anomalies = [a for a in anomalies if not a.recovered]
    recovered_anomalies = _FindAndUpdateRecoveredAnomalies(
        non_recovered_anomalies)

    map(_AddLogForRecoveredAnomaly, recovered_anomalies)

    if all(a.recovered for a in anomalies):
      cls._CommentOnRecoveredBug(bug_id)

  @classmethod
  def _CommentOnRecoveredBug(cls, bug_id):
    """Adds a comment and close the bug on Issue tracker."""
    bug = ndb.Key('Bug', bug_id).get()
    if bug.status != bug_data.BUG_STATUS_OPENED:
      return
    bug.status = bug_data.BUG_STATUS_RECOVERED
    bug.put()
    comment = cls._RecoveredBugComment(bug_id)

    issue_tracker = issue_tracker_service.IssueTrackerService(
        additional_credentials=utils.ServiceAccountCredentials())
    issue_tracker.AddBugComment(bug_id, comment)

  @classmethod
  def _RecoveredBugComment(cls, bug_id):
    server_url = app_identity.get_default_version_hostname()
    graphs_url = 'https://%s/group_report?bug_id=%s' % (server_url, bug_id)
    return 'Automatic message: All alerts recovered.\nGraphs: %s' % graphs_url

  @classmethod
  def _FetchLatestBugs(cls):
    """Fetches recently-created Bug entities."""
    old_timestamp = datetime.datetime.now() - _OLDEST_BUG_DELTA
    query = bug_data.Bug.query(bug_data.Bug.timestamp > old_timestamp)
    return query.fetch()


def _FindAndUpdateRecoveredAnomalies(anomalies):
  """Finds and updates anomalies that recovered."""
  recovered_anomalies = []
  for anomaly_entity in anomalies:
    if _IsAnomalyRecovered(anomaly_entity):
      anomaly_entity.recovered = True
      recovered_anomalies.append(anomaly_entity)
  ndb.put_multi(recovered_anomalies)
  return recovered_anomalies


def _IsAnomalyRecovered(anomaly_entity):
  """Checks whether an Anomaly has recovered.

  An Anomaly will be considered "recovered" if there's a change point in
  the series after the Anomaly with roughly equal magnitude and opposite
  direction.

  Args:
    anomaly_entity: The original regression Anomaly.

  Returns:
    True if the Anomaly should be marked as recovered, False otherwise.
  """
  test = anomaly_entity.GetTestMetadataKey().get()
  if not test:
    logging.error('TestMetadata %s not found for Anomaly %s, deleting test.',
                  utils.TestPath(anomaly_entity.GetTestMetadataKey()),
                  anomaly_entity)
    anomaly_entity.key.delete()
    return False
  config = anomaly_config.GetAnomalyConfigDict(test)
  max_num_rows = config.get(
      'max_window_size', find_anomalies.DEFAULT_NUM_POINTS)
  rows = [r for r in find_anomalies.GetRowsToAnalyze(test, max_num_rows)
          if r.revision > anomaly_entity.end_revision]
  change_points = find_anomalies.FindChangePointsForTest(rows, config)
  delta_anomaly = (anomaly_entity.median_after_anomaly -
                   anomaly_entity.median_before_anomaly)
  for change in change_points:
    delta_change = change.median_after - change.median_before
    if (_IsOppositeDirection(delta_anomaly, delta_change) and
        _IsApproximatelyEqual(delta_anomaly, -delta_change)):
      logging.debug('Anomaly %s recovered; recovery change point %s.',
                    anomaly_entity.key, change.AsDict())
      return True
  return False


def _IsOppositeDirection(delta1, delta2):
  return delta1 * delta2 < 0


def _IsApproximatelyEqual(delta1, delta2):
  smaller = min(delta1, delta2)
  larger = max(delta1, delta2)
  return math_utils.RelativeChange(smaller, larger) <= _MAX_DELTA_DIFFERENCE


def _AddLogForRecoveredAnomaly(anomaly_entity):
  """Adds a quick log entry for an anomaly that has recovered."""
  logging.info('_AddLogForRecoveredAnomaly %s', anomaly_entity.key.id())
  formatter = quick_logger.Formatter()
  sheriff_key = anomaly_entity.GetTestMetadataKey().get().sheriff
  if not sheriff_key:
    return
  sheriff_name = sheriff_key.string_id()
  logger = quick_logger.QuickLogger('auto_triage', sheriff_name, formatter)
  message = ('Alert on %s has recovered. See <a href="%s">graph</a>.%s' %
             (utils.TestPath(anomaly_entity.GetTestMetadataKey()),
              ('https://chromeperf.appspot.com/group_report?keys=' +
               anomaly_entity.key.urlsafe()),
              _BugLink(anomaly_entity)))
  logger.Log(message)
  logger.Save()


def _BugLink(anomaly_entity):
  if anomaly_entity.bug_id > 0:
    bug_id = anomaly_entity.bug_id
    return (' Bug: <a href="https://chromeperf.appspot.com/group_report?'
            'bug_id=%s">%s</a>' % (bug_id, bug_id))
  return ''
