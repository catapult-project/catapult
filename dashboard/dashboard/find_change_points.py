# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A simplified change-point detection algorithm.

Historically, the performance dashboard has used the GASP service for
detection. Brett Schein wrote a simplified version of this algorithm
for the dashboard in Matlab, and this was ported to Python by Dave Tu.

The general goal is to find any increase or decrease which is likely to
represent a real change in the underlying data source.

See: http://en.wikipedia.org/wiki/Step_detection

In 2019, we also integrate a successive bisection with combined Mann-Whitney
U-test and Kolmogorov-Smirnov tests to identify potential change points. This is
not exactly the E-divisive algorithm, but is close enough.

See: https://arxiv.org/abs/1306.4933
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import logging

from dashboard import find_step
from dashboard import ttest
from dashboard.common import math_utils
from dashboard.common import clustering_change_detector

# Maximum number of points to consider at one time.
_MAX_WINDOW_SIZE = 50

# Minimum number of points in a segment. This can help filter out erroneous
# results by ignoring results that were found from looking at too few points.
MIN_SEGMENT_SIZE = 6

# Minimum absolute difference between medians before and after.
_MIN_ABSOLUTE_CHANGE = 0

# Minimum relative difference between medians before and after.
_MIN_RELATIVE_CHANGE = 0.01

# "Steppiness" is a number between 0 and 1 that indicates how similar the
# shape is to a perfect step function, where 1 represents a step function.
_MIN_STEPPINESS = 0.5

# The "standard deviation" is based on a subset of points in the series.
# This parameter is the minimum acceptable ratio of the relative change
# and this standard deviation.
_MULTIPLE_OF_STD_DEV = 2.5


class ChangePoint(
    collections.namedtuple(
        'ChangePoint',
        (
            # The x-value of the first point after a step.
            'x_value',
            # Median of the segments before and after the change point.
            'median_before',
            'median_after',
            # Number of points before and after the change point.
            'size_before',
            'size_after',
            # X-values of the first and last point in the series window used.
            'window_start',
            'window_end',
            # Relative change from before to after.
            'relative_change',
            # Standard deviation of points before.
            'std_dev_before',
            # Results of the Welch's t-test for values before and after.
            't_statistic',
            'degrees_of_freedom',
            'p_value'))):
  """A ChangePoint represents a change in a series -- a potential alert."""
  _slots = None

  def AsDict(self):
    """Returns a dictionary mapping attributes to values."""
    return self._asdict()


def FindChangePoints(series,
                     max_window_size=_MAX_WINDOW_SIZE,
                     min_segment_size=MIN_SEGMENT_SIZE,
                     min_absolute_change=_MIN_ABSOLUTE_CHANGE,
                     min_relative_change=_MIN_RELATIVE_CHANGE,
                     min_steppiness=_MIN_STEPPINESS,
                     multiple_of_std_dev=_MULTIPLE_OF_STD_DEV):
  """Finds change points in the given series.

  Only the last |max_window_size| points are examined, regardless of how many
  points are passed in. The reason why it might make sense to limit the number
  of points to look at is that if there are multiple change-points in the window
  that's looked at, then this function will be less likely to find any of them.

  This uses a clustering change detector (an approximation of E-divisive) in the
  `clustering_change_detector` module.

  Args:
    series: A list of (x, y) pairs.
    max_window_size: Number of points to analyze.
    min_segment_size: Min size of segments before or after change point.
    min_absolute_change: Absolute change threshold.
    min_relative_change: Relative change threshold.
    min_steppiness: Threshold for how similar to a step a change point must be.
    multiple_of_std_dev: Threshold for change as multiple of std. deviation.

  Returns:
    A list with one ChangePoint object, or an empty list.
  """
  if len(series) < 2:
    return []  # Not enough points to possibly contain a valid split point.
  series = series[-max_window_size:]
  _, y_values = zip(*series)

  candidate_indices = []
  split_index = 0

  def RelativeIndexAdjuster(base, offset):
    if base == 0:
      return offset

    # Prevent negative indices.
    return max((base + offset) - min_segment_size, 0)

  # We iteratively find all potential change-points in the range.
  while split_index + min_segment_size < len(y_values):
    try:
      # First we get an adjusted set of indices, starting from split_index,
      # filtering out the ones we've already seen.
      potential_candidates_unadjusted = (
          clustering_change_detector.ClusterAndFindSplit(
              y_values[max(split_index - min_segment_size, 0):]))
      potential_candidates_unfiltered = [
          RelativeIndexAdjuster(split_index, x)
          for x in potential_candidates_unadjusted
      ]
      potential_candidates = [
          x for x in potential_candidates_unfiltered
          if x not in candidate_indices
      ]
      logging.debug('New indices: %s', potential_candidates)

      if potential_candidates:
        candidate_indices.extend(potential_candidates)
        split_index = max(potential_candidates)
      else:
        break
    except clustering_change_detector.Error as e:
      if not candidate_indices:
        logging.warning('Clustering change point detection failed: %s', e)
        return []
      break

  def RevAndIdx(idx):
    return ('rev:%s' % (series[idx][0],), 'idx:%s' % (idx,))

  logging.info('E-Divisive candidate change-points: %s',
               [RevAndIdx(idx) for idx in candidate_indices])
  change_points = []
  for potential_index in reversed(sorted(candidate_indices)):
    passed_filter, reject_reason = _PassesThresholds(
        y_values,
        potential_index,
        min_segment_size=min_segment_size,
        min_absolute_change=min_absolute_change,
        min_relative_change=min_relative_change,
        min_steppiness=min_steppiness,
        multiple_of_std_dev=multiple_of_std_dev)
    if passed_filter:
      change_points.append(potential_index)
    else:
      logging.debug('Rejected %s as potential index (%s); reason = %s',
                    potential_index, RevAndIdx(potential_index), reject_reason)

  logging.info('E-Divisive potential change-points: %s',
               [RevAndIdx(idx) for idx in change_points])
  return [MakeChangePoint(series, index) for index in change_points[0:1]]


def MakeChangePoint(series, split_index):
  """Makes a ChangePoint object for the given series at the given point.

  Args:
    series: A list of (x, y) pairs.
    split_index: Index of the first point after the split.

  Returns:
    A ChangePoint object.
  """
  assert 0 <= split_index < len(series)
  x_values, y_values = zip(*series)
  left, right = y_values[:split_index], y_values[split_index:]
  left_median, right_median = math_utils.Median(left), math_utils.Median(right)
  ttest_results = ttest.WelchsTTest(left, right)
  return ChangePoint(
      x_value=x_values[split_index],
      median_before=left_median,
      median_after=right_median,
      size_before=len(left),
      size_after=len(right),
      window_start=x_values[0],
      window_end=x_values[-1],  # inclusive bound
      relative_change=math_utils.RelativeChange(left_median, right_median),
      std_dev_before=math_utils.StandardDeviation(left),
      t_statistic=ttest_results.t,
      degrees_of_freedom=ttest_results.df,
      p_value=ttest_results.p)


def _PassesThresholds(values, split_index, min_segment_size,
                      min_absolute_change, min_relative_change, min_steppiness,
                      multiple_of_std_dev):
  """Checks whether a point in a series appears to be an change point.

  Args:
    values: A list of numbers.
    split_index: An index in the list of numbers.
    min_segment_size: Threshold for size of segments before or after a point.
    min_absolute_change: Minimum absolute median change threshold.
    min_relative_change: Minimum relative median change threshold.
    min_steppiness: Threshold for how similar to a step a change point must be.
    multiple_of_std_dev: Threshold for change as multiple of std. deviation.

  Returns:
    A tuple of (bool, string) where the bool indicates whether the split index
    passes the thresholds and the string being the reason it did not.
  """
  left, right = values[:split_index], values[split_index:]
  left_median, right_median = math_utils.Median(left), math_utils.Median(right)

  # 1. Segment size filter.
  if len(left) < min_segment_size or len(right) < min_segment_size:
    return (False, 'min_segment_size')

  # 2. Absolute change filter.
  absolute_change = abs(left_median - right_median)
  if absolute_change < min_absolute_change:
    return (False, 'min_absolute_change')

  # 3. Relative change filter.
  relative_change = math_utils.RelativeChange(left_median, right_median)
  if relative_change < min_relative_change:
    return (False, 'min_relative_change')

  # 4. Multiple of standard deviation filter.
  min_std_dev = min(
      math_utils.StandardDeviation(left), math_utils.StandardDeviation(right))
  if absolute_change < multiple_of_std_dev * min_std_dev:
    return (False, 'min_std_dev')

  # 5. Steppiness filter.
  steppiness = find_step.Steppiness(values, split_index)
  if steppiness < min_steppiness:
    return (False, 'min_steppiness')

  # Passed all filters!
  return (True, 'passed')
