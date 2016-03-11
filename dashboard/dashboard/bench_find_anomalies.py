# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A tool to compare functions for finding anomalies to the current default.

This tool provides a way to benchmark an anomaly detection algorithm against
the current find_change_points (base) by running simulations and comparing the
results to the base results and to the existing anomalies in the datastore.

Usage:
  1. Run SetupBaseDataForBench() if not yet.

  2. Add an implementation of find_change_points that takes
  (test_entity, chart_series) arguments and returns a list of
  find_change_points.ChangePoint entities.
  See find_change_points_exp.RunFindChangePoints.

  3. Add that function path to _EXPERIMENTAL_FUNCTIONS with a key name.

  4. Call BenchFindChangePoints(name, description) to add a bench job, where
  name is one of the keys in _EXPERIMENTAL_FUNCTIONS. Name and description
  must be unique for each run. The bench results are logged in quick_logger at:
  chromeperf.appspot.com/get_logs?namespace=bench_find_anomalies&name=report

If you want to clear the base data, you can run DeleteAllTestBenchEntities().

Results:
  Invalid alerts: Number of change points found by the experimental function
      which correspond to invalid alerts, over total invalid alerts.
  Confirmed alerts: Number of change points found by the experimental function
      which correspond to alerts the sheriff filed a bug for, over the total
      number of alerts with bug ID.
  New alerts: Number of alerts found by the experimental function that the base
      find_change_points algorithm did not find.
  Total alerts: Total change points found by the experimental function,
      over the total number of base alerts.
"""

import logging

from pipeline import common as pipeline_common
from pipeline import pipeline

from google.appengine.api import app_identity
from google.appengine.ext import deferred
from google.appengine.ext import ndb

from dashboard import debug_alert
from dashboard import find_change_points
from dashboard import find_change_points_exp
from dashboard import layered_cache
from dashboard import quick_logger
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data

_TASK_QUEUE_NAME = 'find-anomalies-bench-queue'

_FIND_ANOMALIES_BENCH_CACHE_KEY = 'find-anomalies-bench'

# Bench name to path of allowable find anomalies function to benchmark.

_EXPERIMENTAL_FUNCTIONS = {
    'find_change_points_default': find_change_points_exp.RunFindChangePoints,
    'steppiness_0_3': lambda test, series:
                      find_change_points_exp.RunFindChangePoints(
                          test, series, min_steppiness=0.3),
    'steppiness_0_4': lambda test, series:
                      find_change_points_exp.RunFindChangePoints(
                          test, series, min_steppiness=0.4),
    'steppiness_0_5': lambda test, series:
                      find_change_points_exp.RunFindChangePoints(
                          test, series, min_steppiness=0.5),
    'steppiness_0_6': lambda test, series:
                      find_change_points_exp.RunFindChangePoints(
                          test, series, min_steppiness=0.6),
}


_TEST_DATA_SHERIFF = 'Chromium Perf Sheriff'

# 1000 tests and 300 rows take about 3 hours to run SetupBaseDataForBench.
_NUM_TEST_TO_BENCH = 3000

# 250 rows takes about 5 minutes to run find_change_points per task queue task.
# (The AE limit is 10 minutes)
_NUM_ROWS_TO_BENCH = 300

# This is the window size which consists of points before and after the
# Anomaly. If an Anomaly's end revision overlaps another Anomaly's window,
# they are considered the same Anomaly.
_MAX_SEGMENT_SIZE_AROUND_ANOMALY = 4

_REPORT_TEMPLATE = """%(bench_name)s: %(description)s
 Invalid alerts: %(invalid_alerts)s
 Confirmed alerts: %(confirmed_alerts)s
 New alerts: %(new_alerts)s
 Total alerts: %(total_alerts)s

 "Unconfirmed" alerts, i.e. "valid" alerts that were not found by
 the experimental function:
 %(unconfirmed_alert_links)s

 "Extra" alerts, i.e. new alerts found by the experimental function
 that weren't found before:
 %(extra_alert_links)s
"""


class TestBench(ndb.Model):
  """Reference anomaly data for one Test."""

  # Test key.
  test = ndb.KeyProperty()

  # List of tuples of (x_value, y_value) for test.
  data_series = ndb.PickleProperty()

  # List of lists of revisions around Anomaly entities from base run.
  base_anomaly_revs = ndb.PickleProperty()

  # List of lists of revisions around Anomaly entities marked invalid.
  invalid_anomaly_revs = ndb.PickleProperty()

  # List of lists of revisions around Anomaly entities with bug IDs.
  confirmed_anomaly_revs = ndb.PickleProperty()


class SimulateAlertProcessingPipeline(pipeline.Pipeline):

  def run(self, bench_name, test_bench_id):  # pylint: disable=invalid-name
    """Runs one experimental alerting function for one TestBench entity.

    Args:
      bench_name: A string bench name.
      test_bench_id: Integer ID of a TestBench entity.

    Returns:
      A pair (TestBench ID, list of Anomaly dicts). But if the Test
      can't be gotten, this will return (None, None).
    """
    all_change_points = []
    test_bench = TestBench.get_by_id(test_bench_id)
    test = test_bench.test.get()
    # If test doesn't exist anymore, just remove this TestBench entity.
    if not test:
      test_bench.key.delete()
      return None, None

    # Clear the last_alerted_function property because it will be used in
    # the experimental alerting function.
    test.last_alerted_revision = None
    data_series = test_bench.data_series
    for i in xrange(1, len(data_series)):
      find_change_points_func = _EXPERIMENTAL_FUNCTIONS[bench_name]
      change_points = find_change_points_func(test, data_series[0:i])
      change_points = [c for c in change_points if _IsRegression(c, test)]
      all_change_points.extend(change_points)
    logging.debug('Completed alert processing simulation task for bench_name: '
                  '%s, bench_id: %s.', bench_name, test_bench_id)
    return test_bench_id, all_change_points


class GenerateComparisonReportPipeline(pipeline.Pipeline):

  def run(  # pylint: disable=invalid-name
      self, bench_name, description, simulation_results):
    """"Generates a comparison report between experimental and base results.

    Args:
      bench_name: A string bench name.
      description: A string description of this bench job.
      simulation_results: A list of pairs, each of which is a pair
          (TestBench id, change point results), i.e. the return value of
          SimulateAlertProcessingPipeline.run. But, the ChangePoint objects,
          which are named tuple objects, are automatically converted to lists
          because they're implicitly serialized as JSON.
    """
    bench_id_to_change_points_as_lists = dict(simulation_results)
    results = {
        'bench_name': bench_name,
        'description': description,
    }
    total_invalid_alerts = 0
    total_confirmed_alerts = 0
    total_new_alerts = 0
    total_alerts = 0
    total_base_alerts = 0
    total_base_invalid_alerts = 0
    total_base_confirmed_alerts = 0

    unconfirmed_alert_links = []
    extra_alert_links = []

    for bench in TestBench.query().fetch():
      bench_id = bench.key.integer_id()
      if bench_id not in bench_id_to_change_points_as_lists:
        continue
      change_points_as_lists = bench_id_to_change_points_as_lists[bench_id]
      invalid_anomaly_rev_set = _Flatten(bench.invalid_anomaly_revs)
      confirmed_anomaly_rev_set = _Flatten(bench.confirmed_anomaly_revs)
      base_anomaly_rev_set = _Flatten(bench.base_anomaly_revs)
      unconfirmed_alert_links.extend(
          _UnconfirmedAlertLinks(bench, change_points_as_lists))
      extra_alert_links.extend(
          _ExtraAlertLinks(bench, change_points_as_lists))

      for change_point_as_list in change_points_as_lists:
        change_point = find_change_points.ChangePoint(*change_point_as_list)
        end_rev = change_point.x_value
        if end_rev in invalid_anomaly_rev_set:
          total_invalid_alerts += 1
        elif end_rev in confirmed_anomaly_rev_set:
          total_confirmed_alerts += 1
        elif end_rev not in base_anomaly_rev_set:
          total_new_alerts += 1

      total_alerts += len(change_points_as_lists)
      total_base_alerts += len(bench.base_anomaly_revs)
      total_base_invalid_alerts += len(bench.invalid_anomaly_revs)
      total_base_confirmed_alerts += len(bench.confirmed_anomaly_revs)

    results['invalid_alerts'] = (
        '%s/%s' % (total_invalid_alerts, total_base_invalid_alerts))
    results['confirmed_alerts'] = (
        '%s/%s' % (total_confirmed_alerts, total_base_confirmed_alerts))
    results['new_alerts'] = total_new_alerts
    results['total_alerts'] = '%s/%s' % (total_alerts, total_base_alerts)
    results['unconfirmed_alert_links'] = '\n'.join(
        unconfirmed_alert_links[:10])
    results['extra_alert_links'] = '\n'.join(
        extra_alert_links[:10])

    _AddReportToLog(results)

    logging.debug('Completed comparison report for bench_name: %s, '
                  'description: %s. Results: %s', bench_name, description,
                  results)


def _UnconfirmedAlertLinks(bench, change_points_as_lists):
  """Makes a list of URLs to view graphs for "unconfirmed" alerts.

  Here, "unconfirmed" alerts refers to alerts that are in the TestBench
  object (i.e. they were found before and "confirmed") but were not found
  by the experimental find-anomalies function -- they were not "confirmed"
  again by the experimental function, so I'm calling them "unconfirmed".

  Below, bench.confirmed_anomaly_revs is a list of lists of revisions *around*
  a confirmed alert. For example, if an alert was found before at revision
  200 and 300, this list might look like: [[199, 200, 201], [299, 300, 301]].

  Thus, the set of alerts that were "confirmed alerts" before, but not found
  by the experimental function is the central revision for each one of these
  groups where the experimental function didn't find any corresponding alerts.

  Ideally for a good experimental function, we're hoping that these
  "unconfirmed" alerts are all cases where sheriffs triaged the alert wrong and
  it was actually invalid.

  Args:
    bench: One TestBench entity.
    change_points_as_lists: List of lists (which are JSONified ChangePoints).

  Returns:
    A list of URLs, each of which is for a graph for one unconfirmed alert.
  """
  anomaly_revs = {c[0] for c in change_points_as_lists}
  unconfirmed_revs = []
  for confirmed_rev_group in bench.confirmed_anomaly_revs:
    if not anomaly_revs.intersection(confirmed_rev_group):
      # The alert for the this confirmed rev group is "unconfirmed" by the
      # experimental function. It should be added to the list.
      mid_index = len(confirmed_rev_group) / 2
      unconfirmed_revs.append(confirmed_rev_group[mid_index])
  return [_GraphLink(bench.test, rev) for rev in unconfirmed_revs]


def _ExtraAlertLinks(bench, change_points_as_lists):
  """Makes a list of links to view "extra" alerts found.

  Here, an "extra" alert means an alert that was found by the experimental
  function but doesn't coincide with any Anomaly in the datastore, regardless
  of whether that Anomaly would be found by the current default alerting
  function.

  Args:
    bench: A TestBench entity.
    change_points_as_lists: List of lists (which are JSONified ChangePoints).

  Returns:
    A list of URLs, each of which is for a graph for one extra alert.
  """
  anomaly_revs = {c[0] for c in change_points_as_lists}
  confirmed_revs = _Flatten(bench.confirmed_anomaly_revs)
  invalid_revs = _Flatten(bench.invalid_anomaly_revs)
  # Both "confirmed revs" and "invalid revs" are previously fired alerts.
  extra_revs = anomaly_revs.difference(confirmed_revs, invalid_revs)
  return [_GraphLink(bench.test, rev) for rev in extra_revs]


def _GraphLink(test_key, rev):
  """Returns an HTML link to view the graph for an alert."""
  test_path = utils.TestPath(test_key)
  master, bot, test = test_path.split('/', 2)
  query = '?masters=%s&bots=%s&tests=%s&rev=%s' % (master, bot, test, rev)
  return '<a href="https://%s/report%s">%s/%s@%s</a>' % (
      app_identity.get_default_version_hostname(), query, bot, test, rev)


class RunExperimentalChunkPipeline(pipeline.Pipeline):

  def run(self, bench_name, test_bench_ids):  # pylint: disable=invalid-name
    """Runs the experimental find_change_points on each TestBench entity.

    This runs SimulateAlertProcessing in parallel and returns a list of
    the combined results.

    Args:
      bench_name: A string bench name.
      test_bench_ids: List of TestBench IDs.

    Yields:
      Pipeline instance.
    """
    results = []
    for bench_id in test_bench_ids:
      result_future = yield SimulateAlertProcessingPipeline(
          bench_name, bench_id)
      results.append(result_future)
    yield pipeline_common.List(*results)


class RunExperimentalPipeline(pipeline.Pipeline):

  def run(self, bench_name, description):  # pylint: disable=invalid-name
    """The root pipeline that start simulation tasks and generating report.

    This spawns tasks to spawn more tasks that run simulation and executes the
    generate report task on the aggregated the results.

    Args:
      bench_name: A string bench name.
      description: A string description of this bench job.

    Yields:
      Pipeline instance.
    """
    test_bench_keys = TestBench.query().fetch(keys_only=True)
    test_bench_ids = [k.integer_id() for k in test_bench_keys]

    results = []
    # Size of number of taskqueue tasks we want to spawn per pipeline.
    pipeline_chunk_size = 1000
    for i in xrange(0, len(test_bench_ids), pipeline_chunk_size):
      id_chunk = test_bench_ids[i:i + pipeline_chunk_size]
      result_future = yield RunExperimentalChunkPipeline(
          bench_name, id_chunk)
      results.append(result_future)

    combined_results = yield pipeline_common.Extend(*results)
    yield GenerateComparisonReportPipeline(
        bench_name, description, combined_results)


def SetupBaseDataForBench():
  """Adds tasks to queue to create base data for bench."""
  if TestBench.query().fetch(keys_only=True, limit=1):
    raise Exception('Base data already exist.')

  # This will take a while, so we do it in a task queue.
  deferred.defer(_AddCreateTestBenchTasks, _queue=_TASK_QUEUE_NAME)


def BenchFindChangePoints(bench_name, description):
  """Submits a bench job for a bench_name and description.

  Requires an implementation of find_change_points added to
  _EXPERIMENTAL_FUNCTIONS. At least bench_name or description must
  be different for each job.

  Args:
    bench_name: A string bench name which should exist in they keys of
        _EXPERIMENTAL_FUNCTIONS.
    description: A string description of this bench job.

  Raises:
    ValueError: The input was not valid.
    Exception: Not enough data available.
  """
  if bench_name not in _EXPERIMENTAL_FUNCTIONS:
    raise ValueError('%s is not a valid find anomalies bench function.' %
                     bench_name)

  bench_key = '%s.%s' % (bench_name, description)
  submitted_benches = layered_cache.Get(_FIND_ANOMALIES_BENCH_CACHE_KEY)
  if not submitted_benches:
    submitted_benches = {}
  if bench_key in submitted_benches:
    raise ValueError('Bench job for "%s. %s" already in submitted.' %
                     (bench_name, description))

  submitted_benches[bench_key] = True
  layered_cache.Set(_FIND_ANOMALIES_BENCH_CACHE_KEY, submitted_benches)

  # Check if base bench data exist.
  if not TestBench.query().fetch(keys_only=True, limit=1):
    raise Exception('No base data available to bench against.')

  # Add to taskqueue to run simulation.
  stage = RunExperimentalPipeline(bench_name, description)
  stage.start(queue_name=_TASK_QUEUE_NAME)


def DeleteAllTestBenchEntities():
  """Deletes all TestBench data."""
  ndb.delete_multi(TestBench.query().fetch(keys_only=True))


def _AddCreateTestBenchTasks():
  """Adds _CreateTestBench tasks to queue."""
  sheriff_key = ndb.Key('Sheriff', _TEST_DATA_SHERIFF)
  query = graph_data.Test.query(
      graph_data.Test.sheriff == sheriff_key,
      graph_data.Test.has_rows == True,
      graph_data.Test.deprecated == False)

  tests = query.fetch(limit=_NUM_TEST_TO_BENCH)

  tests = [t for t in tests if _GetSheriffForTest(t) and not _IsRefBuild(t)]
  for test in tests:
    deferred.defer(_CreateTestBench, test.key, _queue=_TASK_QUEUE_NAME)


def _CreateTestBench(test_key):
  """Fetches and stores test and row data that would be used to run bench."""
  # Get rows entity.
  query = graph_data.Row.query(projection=['revision', 'value'])
  query = query.filter(graph_data.Row.parent_test == test_key)
  query = query.order(-graph_data.Row.revision)
  rows = list(reversed(query.fetch(limit=_NUM_ROWS_TO_BENCH)))
  data_series = [(row.revision, row.value) for row in rows]

  # Add TestBench entity.
  test_bench = TestBench(test=test_key, data_series=data_series)
  _UpdateInvalidAndConfirmedAnomalyRevs(test_bench)
  _RunBaseAlertProcessing(test_bench)
  test_bench.put()


def _AddReportToLog(report_dict):
  """Adds a log for bench results."""
  report = _REPORT_TEMPLATE % report_dict
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger(
      'bench_find_anomalies', 'report', formatter)
  logger.Log(report)
  logger.Save()


def _Flatten(list_of_list):
  """Creates set of all items in the sublists."""
  flattened = set()
  for item in list_of_list:
    flattened.update(item)
  return flattened


def _UpdateInvalidAndConfirmedAnomalyRevs(test_bench):
  """Updates TestBench entity with invalid and confirmed anomalies revs."""

  # Start rev for getting Anomalies should be at min_segment_size.
  test = test_bench.test.get()
  config_dict = anomaly_config.GetAnomalyConfigDict(test)
  min_segment_size = config_dict.get(
      'min_segment_size', find_change_points.MIN_SEGMENT_SIZE)
  start_index = min(min_segment_size, len(test_bench.data_series)) - 1
  start_rev = test_bench.data_series[start_index][0]

  query = anomaly.Anomaly.query(anomaly.Anomaly.test == test_bench.test)
  anomalies = query.fetch()
  anomalies.sort(key=lambda a: a.end_revision)
  anomalies = [a for a in anomalies if a.end_revision >= start_rev and
               not a.is_improvement]

  test_bench.invalid_anomaly_revs = [
      _GetRevsAroundRev(test_bench.data_series, a.end_revision)
      for a in anomalies if a.bug_id == -1]
  test_bench.confirmed_anomaly_revs = [
      _GetRevsAroundRev(test_bench.data_series, a.end_revision)
      for a in anomalies if a.bug_id > 0]


def _RunBaseAlertProcessing(test_bench):
  """Runs base alert processing simulation on TestBench entity.

  This function runs the current find_change_points.FindChangePoints
  implementation and saves the revisions around the found anomalies to
  a TestBench entity.

  Args:
    test_bench: A TestBench entity.
  """
  test = test_bench.test.get()
  config_dict = anomaly_config.GetAnomalyConfigDict(test)
  change_points = debug_alert.SimulateAlertProcessing(
      test_bench.data_series, **config_dict)

  test_bench.base_anomaly_revs = [
      _GetRevsAroundRev(test_bench.data_series, change_point.x_value)
      for change_point in change_points if _IsRegression(change_point, test)]


def _GetRevsAroundRev(data_series, revision):
  """Gets a list of revisions from before to after a given revision.

  Args:
    data_series: A list of (revision, value).
    revision: A revision number.

  Returns:
    A list of revisions.
  """
  if not _MAX_SEGMENT_SIZE_AROUND_ANOMALY:
    return [revision]

  middle_index = 0
  for i in xrange(len(data_series)):
    if data_series[i][0] == revision:
      middle_index = i
      break
  start_index = max(0, middle_index - _MAX_SEGMENT_SIZE_AROUND_ANOMALY)
  end_index = middle_index + _MAX_SEGMENT_SIZE_AROUND_ANOMALY + 1
  series_around_rev = data_series[start_index:end_index]
  return [s[0] for s in series_around_rev]


def _IsRefBuild(test):
  """Returns True if test is a reference build."""
  key_path = test.key.string_id()
  return key_path[-1] == 'ref' or key_path[-1].endswith('_ref')


def _GetSheriffForTest(test):
  """Gets the Sheriff for a test, or None if no sheriff."""
  if test.sheriff:
    return test.sheriff.get()
  return None


def _IsRegression(change_point, test):
  """Returns whether the alert is a regression for the given test.

  Args:
    change_point: A find_change_points.ChangePoint object.
    test: Test to get the regression direction for.

  Returns:
    True if it is a regression anomaly, otherwise False.
  """
  median_before = change_point.median_before
  median_after = change_point.median_after
  if (median_before < median_after and
      test.improvement_direction == anomaly.UP):
    return False
  if (median_before >= median_after and
      test.improvement_direction == anomaly.DOWN):
    return False
  return True
