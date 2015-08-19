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
from dashboard import rietveld_service
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

# Default parameters used when deciding whether or not an alert should
# be considered recovered, if not overridden by the anomaly threshold
# config of a test. These may be, but are not necessarily, the same as
# the related constants in the find_change_points module.
# TODO(qyearsley): If possible, simplify _IsAnomalyRecovered so that
# these values are no longer needed, or change it to use a method in
# find_change_points.
_DEFAULT_MULTIPLE_OF_STD_DEV = 3.5
_DEFAULT_MIN_RELATIVE_CHANGE = 0.01
_DEFAULT_MIN_ABSOLUTE_CHANGE = 0.0


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

    TriageAnomalies.Process()
    TriageBugs.Process()


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
      if bug.status == bug_data.BUG_STATUS_OPENED:
        taskqueue.add(
            url='/auto_triage',
            params={'update_recovered_bug': True, 'bug_id': bug.key.id()},
            queue_name=_TASK_QUEUE_NAME)

  @classmethod
  def UpdateRecoveredBugs(cls, bug_id):
    """Checks whether anomalies with bug_id have recovered."""
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

    credentials = rietveld_service.Credentials(
        rietveld_service.GetDefaultRietveldConfig(),
        rietveld_service.PROJECTHOSTING_SCOPE)
    issue_tracker = issue_tracker_service.IssueTrackerService(
        additional_credentials=credentials)
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
    is_recovered, measurements = _IsAnomalyRecovered(anomaly_entity)
    if is_recovered:
      anomaly_entity.recovered = True
      recovered_anomalies.append(anomaly_entity)
      logging.debug('Anomaly %s recovered with measurements %s.',
                    anomaly_entity.key, measurements)
  ndb.put_multi(recovered_anomalies)
  return recovered_anomalies


def _IsAnomalyRecovered(anomaly_entity):
  """Checks whether anomaly has recovered.

  We have the measurements for the segment before the anomaly.  If we take
  the measurements for the latest segment after the anomaly, we can find if
  the anomaly recovered.

  Args:
    anomaly_entity: The original regression anomaly.

  Returns:
    A tuple (is_anomaly_recovered, measurements), where is_anomaly_recovered
    is True if anomaly has recovered, and measurements is dictionary
    of name to value of measurements used to evaluate if anomaly recovered.
    measurements is None if anomaly has not recovered.
  """
  # 1. Check if the Anomaly entity has std_dev_before_anomaly and
  #    window_end_revision properties which we're using to decide whether or
  #    not it is recovered.
  if (anomaly_entity.std_dev_before_anomaly is None or
      anomaly_entity.window_end_revision is None):
    return False, None

  test = anomaly_entity.test.get()
  config = anomaly_config.GetAnomalyConfigDict(test)
  latest_rows = find_anomalies.GetRowsToAnalyze(
      test, anomaly_entity.segment_size_after)
  latest_values = [row.value for row in latest_rows
                   if row.revision > anomaly_entity.window_end_revision]

  # 2. Segment size filter.
  if len(latest_values) < anomaly_entity.segment_size_after:
    return False, None

  median_before = anomaly_entity.median_before_anomaly
  median_after = math_utils.Median(latest_values)
  std_dev_before = anomaly_entity.std_dev_before_anomaly
  std_dev_after = math_utils.StandardDeviation(latest_values)
  multiple_of_std_dev = config.get('multiple_of_std_dev',
                                   _DEFAULT_MULTIPLE_OF_STD_DEV)
  min_relative_change = config.get('min_relative_change',
                                   _DEFAULT_MIN_RELATIVE_CHANGE)
  min_absolute_change = config.get('min_absolute_change',
                                   _DEFAULT_MIN_ABSOLUTE_CHANGE)

  # If no improvement direction is provided, use absolute changes.
  if test.improvement_direction == anomaly.UNKNOWN:
    absolute_change = abs(median_after - median_before)
    relative_change = abs(_RelativeChange(median_before, median_after))
  else:
    if test.improvement_direction == anomaly.UP:
      direction = -1
    else:
      direction = 1
    absolute_change = direction * (median_after - median_before)
    relative_change = direction * _RelativeChange(median_before, median_after)

  measurements = {
      'segment_size_after': anomaly_entity.segment_size_after,
      'window_end_revision': anomaly_entity.window_end_revision,
      'median_before': median_before,
      'median_after': median_after,
      'std_dev_before': std_dev_before,
      'std_dev_after': std_dev_after,
      'multiple_of_std_dev': multiple_of_std_dev,
      'min_relative_change': min_relative_change,
      'min_absolute_change': min_absolute_change,
      'absolute_change': absolute_change,
      'relative_change': relative_change,
  }

  # 3. If it's an improvement, return.
  if absolute_change <= 0:
    return True, measurements

  # 4. Absolute change filter.
  if min_absolute_change > 0 and absolute_change >= min_absolute_change:
    return False, None

  # 5. Relative change filter.
  if relative_change >= min_relative_change:
    return False, None

  # 6. Standard deviation filter.
  min_std_dev = min(std_dev_before, std_dev_after)
  if absolute_change > min_std_dev:
    return False, None

  return True, measurements


def _RelativeChange(before, after):
  """Returns the none absolute value of the relative change between two values.

  Args:
    before: First value.
    after: Second value.

  Returns:
    Relative change from the first to the second value.
  """
  return (after - before) / float(before) if before != 0 else float('inf')


def _AddLogForRecoveredAnomaly(anomaly_entity, bug_id=None):
  """Adds a log for an anomaly that has recovered."""
  sheriff_key = anomaly_entity.test.get().sheriff
  if not sheriff_key:
    return
  sheriff_name = sheriff_key.string_id()
  html_str = 'Alert on %s has recovered.%s See <a href="%s">graph</a>.'
  alert_url = ('https://chromeperf.appspot.com/group_report?keys=' +
               anomaly_entity.key.urlsafe())
  bug_link = ''
  if bug_id:
    bug_link = (' Bug: <a href="https://chromeperf.appspot.com/group_report?'
                'bug_id=%s">%s</a>' % (bug_id, bug_id))

  test_path = utils.TestPath(anomaly_entity.test)
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('auto_triage', sheriff_name, formatter)
  logger.Log(html_str, test_path, bug_link, alert_url)
  logger.Save()
