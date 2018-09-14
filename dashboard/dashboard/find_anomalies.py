# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Processes tests and creates new Anomaly entities.

This module contains the ProcessTest function, which searches the recent
points in a test for potential regressions or improvements, and creates
new Anomaly entities.
"""

import logging

from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard import email_sheriff
from dashboard import find_change_points
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.models import histogram
from tracing.value.diagnostics import reserved_infos

# Number of points to fetch and pass to FindChangePoints. A different number
# may be used if a test has a "max_window_size" anomaly config parameter.
DEFAULT_NUM_POINTS = 50

@ndb.synctasklet
def ProcessTests(test_keys):
  """Processes a list of tests to find new anoamlies.

  Args:
    test_keys: A list of TestMetadata ndb.Key's.
  """
  yield ProcessTestsAsync(test_keys)


@ndb.tasklet
def ProcessTestsAsync(test_keys):
  # Using a parallel yield here let's the tasklets for each _ProcessTest run
  # in parallel.
  yield [_ProcessTest(k) for k in test_keys]


@ndb.tasklet
def _ProcessTest(test_key):
  """Processes a test to find new anomalies.

  Args:
    test_key: The ndb.Key for a TestMetadata.
  """
  test = yield test_key.get_async()

  sheriff = yield _GetSheriffForTest(test)
  if not sheriff:
    logging.error('No sheriff for %s', test_key)
    raise ndb.Return(None)

  config = yield anomaly_config.GetAnomalyConfigDictAsync(test)
  max_num_rows = config.get('max_window_size', DEFAULT_NUM_POINTS)
  rows_by_stat = yield GetRowsToAnalyzeAsync(test, max_num_rows)

  ref_rows_by_stat = {}
  ref_test = yield _CorrespondingRefTest(test_key)
  if ref_test:
    ref_rows_by_stat = yield GetRowsToAnalyzeAsync(ref_test, max_num_rows)

  for s, rows in rows_by_stat.iteritems():
    if rows:
      yield _ProcesssTestStat(
          config, sheriff, test, s, rows, ref_rows_by_stat.get(s))


def _EmailSheriff(sheriff_key, test_key, anomaly_key):
  sheriff_entity = sheriff_key.get()
  test_entity = test_key.get()
  anomaly_entity = anomaly_key.get()

  email_sheriff.EmailSheriff(sheriff_entity, test_entity, anomaly_entity)


@ndb.tasklet
def _ProcesssTestStat(config, sheriff, test, stat, rows, ref_rows):
  test_key = test.key

  # If there were no rows fetched, then there's nothing to analyze.
  if not rows:
    logging.error('No rows fetched for %s', test.test_path)
    raise ndb.Return(None)

  # Get anomalies and check if they happen in ref build also.
  change_points = FindChangePointsForTest(rows, config)

  if ref_rows:
    ref_change_points = FindChangePointsForTest(ref_rows, config)

    # Filter using any jumps in ref
    change_points = _FilterAnomaliesFoundInRef(
        change_points, ref_change_points, test_key)

  anomalies = yield [
      _MakeAnomalyEntity(c, test, stat, rows) for c in change_points]

  # If no new anomalies were found, then we're done.
  if not anomalies:
    raise ndb.Return(None)

  logging.info('Created %d anomalies', len(anomalies))
  logging.info(' Test: %s', test_key.id())
  logging.info(' Stat: %s', stat)
  logging.info(' Sheriff: %s', test.sheriff.id())

  yield ndb.put_multi_async(anomalies)

  # TODO(simonhatch): email_sheriff.EmailSheriff() isn't a tasklet yet, so this
  # code will run serially.
  # Email sheriff about any new regressions.
  for anomaly_entity in anomalies:
    if (anomaly_entity.bug_id is None and
        not anomaly_entity.is_improvement and
        not sheriff.summarize):
      deferred.defer(_EmailSheriff, sheriff.key, test.key, anomaly_entity.key)


@ndb.tasklet
def _FindLatestAlert(test, stat):
  query = anomaly.Anomaly.query()
  query = query.filter(anomaly.Anomaly.test == test.key)
  query = query.filter(anomaly.Anomaly.statistic == stat)
  query = query.order(-anomaly.Anomaly.end_revision)
  results = yield query.get_async()
  if not results:
    raise ndb.Return(None)
  raise ndb.Return(results)


@ndb.tasklet
def _FindMonitoredStatsForTest(test):
  del test
  # TODO: This will get filled out after refactor.
  raise ndb.Return(['avg'])


@ndb.synctasklet
def GetRowsToAnalyze(test, max_num_rows):
  """Gets the Row entities that we want to analyze.

  Args:
    test: The TestMetadata entity to get data for.
    max_num_rows: The maximum number of points to get.

  Returns:
    A list of the latest Rows after the last alerted revision, ordered by
    revision. These rows are fetched with t a projection query so they only
    have the revision and value properties.
  """
  result = yield GetRowsToAnalyzeAsync(test, max_num_rows)
  raise ndb.Return(result)


@ndb.tasklet
def GetRowsToAnalyzeAsync(test, max_num_rows):
  # If this is a histogram based test, there may be multiple statistics we want
  # to analyze
  alerted_stats = yield _FindMonitoredStatsForTest(test)

  latest_alert_by_stat = dict(
      (s, _FindLatestAlert(test, s)) for s in alerted_stats)

  results = {}
  for s in alerted_stats:
    results[s] = _FetchRowsByStat(
        test.key, s, latest_alert_by_stat[s], max_num_rows)

  for s in results.iterkeys():
    results[s] = yield results[s]

  raise ndb.Return(results)


@ndb.tasklet
def _FetchRowsByStat(test_key, stat, last_alert_future, max_num_rows):
  # If stats are specified, we only want to alert on those, otherwise alert on
  # everything.
  if stat == 'avg':
    query = graph_data.Row.query(projection=['revision', 'value'])
  else:
    query = graph_data.Row.query()

  query = query.filter(
      graph_data.Row.parent_test == utils.OldStyleTestKey(test_key))

  # The query is ordered in descending order by revision because we want
  # to get the newest points.
  if last_alert_future:
    last_alert = yield last_alert_future
    if last_alert:
      query = query.filter(graph_data.Row.revision > last_alert.end_revision)
  query = query.order(-graph_data.Row.revision)

  # However, we want to analyze them in ascending order.
  rows = yield query.fetch_async(limit=max_num_rows)

  vals = []
  for r in list(reversed(rows)):
    if stat == 'avg':
      vals.append((r.revision, r, r.value))
    elif stat == 'std':
      vals.append((r.revision, r, r.error))
    else:
      vals.append((r.revision, r, getattr(r, 'd_%s' % stat)))

  raise ndb.Return(vals)


def _FilterAnomaliesFoundInRef(change_points, ref_change_points, test):
  change_points_filtered = []
  test_path = utils.TestPath(test)
  for c in change_points:
    # Log information about what anomaly got filtered and what did not.
    if not _IsAnomalyInRef(c, ref_change_points):
      logging.info('Nothing was filtered out for test %s, and revision %s',
                   test_path, c.x_value)
      change_points_filtered.append(c)
    else:
      logging.info('Filtering out anomaly for test %s, and revision %s',
                   test_path, c.x_value)
  return change_points_filtered


@ndb.tasklet
def _CorrespondingRefTest(test_key):
  """Returns the TestMetadata for the corresponding ref build trace, or None."""
  test_path = utils.TestPath(test_key)
  possible_ref_test_paths = [test_path + '_ref', test_path + '/ref']
  for path in possible_ref_test_paths:
    ref_test = yield utils.TestKey(path).get_async()
    if ref_test:
      raise ndb.Return(ref_test)
  raise ndb.Return(None)


def _IsAnomalyInRef(change_point, ref_change_points):
  """Checks if anomalies are detected in both ref and non ref build.

  Args:
    change_point: A find_change_points.ChangePoint object to check.
    ref_change_points: List of find_change_points.ChangePoint objects
        found for a ref build series.

  Returns:
    True if there is a match found among the ref build series change points.
  """
  for ref_change_point in ref_change_points:
    if change_point.x_value == ref_change_point.x_value:
      return True
  return False


@ndb.tasklet
def _GetSheriffForTest(test):
  """Gets the Sheriff for a test, or None if no sheriff."""
  if test.sheriff:
    sheriff = yield test.sheriff.get_async()
    raise ndb.Return(sheriff)
  raise ndb.Return(None)


def _GetImmediatelyPreviousRevisionNumber(later_revision, rows):
  """Gets the revision number of the Row immediately before the given one.

  Args:
    later_revision: A revision number.
    rows: List of Row entities in ascending order by revision.

  Returns:
    The revision number just before the given one.
  """
  for (revision, _, _) in reversed(rows):
    if revision < later_revision:
      return revision
  assert False, 'No matching revision found in |rows|.'


def _GetRefBuildKeyForTest(test):
  """TestMetadata key of the reference build for the given test, if one exists.

  Args:
    test: the TestMetadata entity to get the ref build for.

  Returns:
    A TestMetadata key if found, or None if not.
  """
  potential_path = '%s/ref' % test.test_path
  potential_test = utils.TestKey(potential_path).get()
  if potential_test:
    return potential_test.key
  potential_path = '%s_ref' % test.test_path
  potential_test = utils.TestKey(potential_path).get()
  if potential_test:
    return potential_test.key
  return None


def _GetDisplayRange(old_end, rows):
  """Get the revision range using a_display_rev, if applicable.

  Args:
    old_end: the x_value from the change_point
    rows: List of Row entities in asscending order by revision.

  Returns:
    A end_rev, start_rev tuple with the correct revision.
  """
  start_rev = end_rev = 0
  for (revision, row, _) in reversed(rows):
    if (revision == old_end and
        hasattr(row, 'r_commit_pos')):
      end_rev = row.r_commit_pos
    elif (revision < old_end and
          hasattr(row, 'r_commit_pos')):
      start_rev = row.r_commit_pos + 1
      break
  if not end_rev or not start_rev:
    end_rev = start_rev = None
  return start_rev, end_rev


@ndb.tasklet
def _MakeAnomalyEntity(change_point, test, stat, rows):
  """Creates an Anomaly entity.

  Args:
    change_point: A find_change_points.ChangePoint object.
    test: The TestMetadata entity that the anomalies were found on.
    stat: The TestMetadata stat that the anomaly was found on.
    rows: List of Row entities that the anomalies were found on.

  Returns:
    An Anomaly entity, which is not yet put in the datastore.
  """
  end_rev = change_point.x_value
  start_rev = _GetImmediatelyPreviousRevisionNumber(end_rev, rows) + 1
  display_start = display_end = None
  if test.master_name == 'ClankInternal':
    display_start, display_end = _GetDisplayRange(change_point.x_value, rows)
  median_before = change_point.median_before
  median_after = change_point.median_after

  suite_key = test.key.id().split('/')[:3]
  suite_key = '/'.join(suite_key)
  suite_key = utils.TestKey(suite_key)

  queried_diagnostics = yield (
      histogram.SparseDiagnostic.GetMostRecentDataByNamesAsync(
          suite_key, set([reserved_infos.BUG_COMPONENTS.name,
                          reserved_infos.OWNERS.name])))

  bug_components = queried_diagnostics.get(
      reserved_infos.BUG_COMPONENTS.name, {}).get('values')

  ownership_information = {
      'emails': queried_diagnostics.get(
          reserved_infos.OWNERS.name, {}).get('values'),
      'component': (bug_components[0] if bug_components else None)}

  new_anomaly = anomaly.Anomaly(
      start_revision=start_rev,
      end_revision=end_rev,
      median_before_anomaly=median_before,
      median_after_anomaly=median_after,
      segment_size_before=change_point.size_before,
      segment_size_after=change_point.size_after,
      window_end_revision=change_point.window_end,
      std_dev_before_anomaly=change_point.std_dev_before,
      t_statistic=change_point.t_statistic,
      degrees_of_freedom=change_point.degrees_of_freedom,
      p_value=change_point.p_value,
      is_improvement=_IsImprovement(test, median_before, median_after),
      ref_test=_GetRefBuildKeyForTest(test),
      test=test.key,
      statistic=stat,
      sheriff=test.sheriff,
      internal_only=test.internal_only,
      units=test.units,
      display_start=display_start,
      display_end=display_end,
      ownership=ownership_information)
  raise ndb.Return(new_anomaly)

def FindChangePointsForTest(rows, config_dict):
  """Gets the anomaly data from the anomaly detection module.

  Args:
    rows: The Row entities to find anomalies for, sorted backwards by revision.
    config_dict: Anomaly threshold parameters as a dictionary.

  Returns:
    A list of find_change_points.ChangePoint objects.
  """
  data_series = [(revision, value) for (revision, _, value) in rows]
  return find_change_points.FindChangePoints(data_series, **config_dict)


def _IsImprovement(test, median_before, median_after):
  """Returns whether the alert is an improvement for the given test.

  Args:
    test: TestMetadata to get the improvement direction for.
    median_before: The median of the segment immediately before the anomaly.
    median_after: The median of the segment immediately after the anomaly.

  Returns:
    True if it is improvement anomaly, otherwise False.
  """
  if (median_before < median_after and
      test.improvement_direction == anomaly.UP):
    return True
  if (median_before >= median_after and
      test.improvement_direction == anomaly.DOWN):
    return True
  return False
