# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides functionality for bisecting a group of anomalies.

This involves choosing an appropriate platform, command, metric and revision
range given a set of different Anomaly entities. The platform to chosen could
depend on current bisect bot status and general bot reliability.

TODO(qyearsley): Use the request handler in this module to provide bisect
parameters on the /bug_report page.
"""

import json

from google.appengine.ext import ndb

from dashboard import request_handler
from dashboard import start_try_job
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data

# Maximum number of Anomaly entities to fetch for a bug.
_FETCH_LIMIT = 512


class BisectGroupHandler(request_handler.RequestHandler):
  """A request handler to choose some bisect parameters.

  TODO(qyearsley): Actually use this module when requesting bisect config
  from the front-end. As of now (April 2015), this handler is not used.
  """

  def get(self):
    """A GET request is the same as a POST for this endpoint."""
    self.post()

  def post(self):
    """Chooses parameters for a bisect job for a group of alerts.

    Request parameters:
      keys: Comma-separated list of urlsafe Anomaly keys (optional).
      bug_id: A bug number (optional, used if keys is not given).

    Outputs:
      If successful, A dictionary of bisect job parameters, encoded as JSON.
      If there was an error or invalid input, an error message.
    """
    # Get the parameters and check that at least one was passed.
    keys = self.request.get('keys')
    bug_id = self.request.get('bug_id')

    # Get the list of anomaly entities from the parameters.
    if keys:
      keys = [ndb.Key(urlsafe=k) for k in keys.split(',')]
      anomalies = ndb.get_multi(keys)
    elif bug_id:
      bug_id = int(bug_id)
      anomalies = anomaly.Anomaly.query(
          anomaly.Anomaly.bug_id == bug_id).fetch(limit=_FETCH_LIMIT)
    else:
      self.ReportError('Neither keys nor bug_id parameter given.', 400)
      return

    # Choose parameters and return the result as JSON.
    params = _ChooseBisectParameters(anomalies)
    self.response.write(json.dumps(params))


def _ChooseBisectParameters(anomalies, next_best_test_index=None):
  """Returns a dictionary with parameters to use for a bisect job.

  Args:
    anomalies: A list of Anomaly entities.
    next_best_test_index: Integer of the next best test to get.

  Returns:
    A dictionary mapping bisect configuration parameter names to values.
    This will include the keys: "bisect_bot", "command", "metric",
    "good_revision", and "bad_revision", or an empty dictionary if no valid
    bisect config can be created.
  """
  if not anomalies:
    return {}
  test = ChooseTest(anomalies, next_best_test_index)
  if not test:
    return {}
  bisect_bot = start_try_job.GuessBisectBot(test.bot_name)
  metric = start_try_job.GuessMetric(test.test_path)
  command = start_try_job.GuessCommand(
      bisect_bot, test.suite_name, metric=metric)
  good, bad = ChooseRevisionRange(anomalies)

  # If not all of the parameters are available, no valid config can be made.
  if not all([test, bisect_bot, command, metric, good, bad]):
    return {}

  return {
      'bisect_bot': bisect_bot,
      'command': command,
      'metric': metric,
      'good_revision': good,
      'bad_revision': bad,
  }


def ChooseTest(anomalies, next_best_test_index=None):
  """Chooses a test to use for a bisect job.

  The particular Test chosen determines the command and metric name that is
  chosen. The test to choose could depend on which of the anomalies has the
  largest regression size.

  Ideally, the choice of bisect bot to use should be based on bisect bot queue
  length, and the choice of metric should be based on regression size and noise
  level.

  However, we don't choose bisect bot and metric independently, since some
  regressions only happen for some tests on some platforms; we should generally
  only bisect with a given bisect bot on a given metric if we know that the
  regression showed up on that platform for that metric.

  Args:
    anomalies: A non-empty list of Anomaly entities.
    next_best_test_index: Integer of the next best test to get.

  Returns:
    A Test entity.
  """
  if not next_best_test_index:
    next_best_test_index = 0
  elif next_best_test_index >= len(anomalies):
    return None

  anomalies.sort(cmp=_CompareAnomalyBisectability)

  for anomaly_entity in anomalies[next_best_test_index:]:
    test_path = utils.TestPath(anomaly_entity.test)
    if start_try_job.CheckBisectability(
        anomaly_entity.start_revision,
        anomaly_entity.end_revision,
        test_path) is None:
      return anomaly_entity.test.get()
  return None


def _CompareAnomalyBisectability(a1, a2):
  """Compares two Anomalies to decide which Anomaly's Test is better to use.

  TODO(qyearsley): Take other factors into account:
   - Consider bisect bot queue length. Note: If there's a simple API to fetch
     this from build.chromium.org, that would be best; even if there is not,
     it would be possible to fetch the HTML page for the builder and check the
     pending list from that.
   - Prefer some platforms over others. For example, bisects on Linux may run
     faster; also, if we fetch info from build.chromium.org, we can check recent
     failures.
   - Consider test run time. This may not be feasible without using a list
     of approximate test run times for different test suites.
   - Consider stddev of test; less noise -> more reliable bisect.

  Args:
    a1: The first Anomaly entity.
    a2: The second Anomaly entity.

  Returns:
    Negative integer if a1 is better than a2, positive integer if a2 is better
    than a1, or zero if they're equally good.
  """
  if a1.percent_changed > a2.percent_changed:
    return -1
  elif a1.percent_changed < a2.percent_changed:
    return 1
  return 0


def ChooseRevisionRange(anomalies):
  """Chooses a revision range to use for a bisect job.

  Note that the first number in the chosen revision range is the "last known
  good" revision, whereas the start_revision property of an Anomaly is the
  "first possible bad" revision.

  If the given set of anomalies is non-overlapping, the revision range chosen
  should be the intersection of the ranges.

  Args:
    anomalies: A non-empty list of Anomaly entities.

  Returns:
    A pair of revision numbers (good, bad), or (None, None) if no valid
    revision range can be chosen.
  """
  good_rev, good_test = max((a.start_revision - 1, a.test) for a in anomalies)
  bad_rev, bad_test = min((a.end_revision, a.test) for a in anomalies)
  if good_rev < bad_rev:
    good = _GetBisectRevision(good_rev, good_test)
    bad = _GetBisectRevision(bad_rev, bad_test)
    return (good, bad)

  # The ranges are non-overlapping. Don't try this bisect.
  return (None, None)


def _GetBisectRevision(revision, test_key):
  """Gets a start or end "revision" value which can be used when bisecting.

  The bisect script takes either Chromium SVN revisions or Chromium git hashes,
  but cannot take timestamps or other types of revision numbers.

  Args:
    revision: The ID of a Row, not necessarily an actual revision number.
    test_key: The ndb.Key for a Test.

  Returns:
    A SVN revision or git SHA1 hash (or the original revision).
  """
  # First try to get a git hash from a corresponding Row entity.
  # Below we try to get Rows directly without querying for efficiency.
  row_parent_key = utils.GetTestContainerKey(test_key)
  row = graph_data.Row.get_by_id(revision, parent=row_parent_key)

  # If the revision is a 6-digit number, just return it.
  if 99999 < revision < 1000000:
    return revision

  if row:
    # The property r_chromium if it exists could be a SVN revision or git hash;
    # The property r_chromium_git if it exists is certainly a git hash.
    if hasattr(row, 'r_chromium_git'):
      return row.r_chromium_git
    if hasattr(row, 'r_chromium'):
      return row.r_chromium

  return None
