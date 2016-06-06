# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Contains experimental alerting functions."""

from dashboard import find_change_points
from dashboard.models import anomaly_config


def RunFindChangePoints(
    test, series, find_change_points_func=find_change_points.FindChangePoints,
    **kwargs):
  """Runs an change-point-finding function on part of a data series.

  This function will be repeatedly called by SimulateAlertProcessingPipeline
  in the bench_find_change_points module with the same TestMetadata entity but
  with more and more points added to the end.

  This is meant to imitate the current behavior of FindChangePoints on the perf
  dashboard.

  Args:
    test: A graph_data.TestMetadata entity.
    series: A list of ordered (x, y) pairs.
    find_change_points_func: A function that has the same interface as
        find_change_points.FindChangePoints.
    **kwargs: Extra parameters to add to the anomaly config dict.

  Returns:
    A list of objects with the property x_value.
  """
  # The anomaly threshold config dictionary determines how many points are
  # analyzed and how far apart alerts should be, as well as other thresholds.
  config = anomaly_config.GetAnomalyConfigDict(test)
  config.update(kwargs)

  # |series| contains all data so far in the TestMetadata, but typically when
  # a test is processed (in find_anomalies.ProcessTest) only the last "window"
  # of points is looked at. This window size depends on the test. To get the
  # same behavior as the current default, we take only the last window.
  series = _GetLastWindow(series, config.get('max_window_size'))
  if len(series) < 2:
    return []

  # Find anomalies for the requested test.
  change_points = find_change_points_func(series, **config)

  return _RemoveKnownAnomalies(test, change_points)


def _GetLastWindow(series, window_size):
  """Returns the last "window" of points in the data series."""
  if not window_size:
    return series
  return series[-window_size:]


def _RemoveKnownAnomalies(test, change_points):
  """Removes some anomalies and updates the given TestMetadata entity.

  Args:
    test: A TestMetadata entity, which has a property last_alerted_revision.
        This property will be updated when this function is called.
    change_points: A list of find_change_points.ChangePoint objects. It is
        assumed that this list is sorted by the x_value property.

  Returns:
    A list of objects with the property x_value.
  """
  # Avoid duplicates.
  if test.last_alerted_revision:
    change_points = [c for c in change_points
                     if c.x_value > test.last_alerted_revision]

  if change_points:
    # No need to call put(). The given TestMetadata entity will be re-used and
    # we don't want to modify TestMetadata entity in the datastore.
    test.last_alerted_revision = change_points[-1].x_value

  return change_points


def FindChangePointsWithAbsoluteChangeThreshold(test, series):
  """Runs FindChangePoints, always setting an absolute change threshold."""
  return RunFindChangePoints(
      test, series,
      max_window_size=50,
      multiple_of_std_dev=3.5,
      min_relative_change=0.1,
      min_absolute_change=1.0,
      min_segment_size=6)
