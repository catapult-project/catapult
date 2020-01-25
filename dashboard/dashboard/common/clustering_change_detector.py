# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""An approximation of the E-Divisive change detection algorithm.

This module implements the constituent functions and components for a change
detection module for time-series data. It derives heavily from the paper [0] on
E-Divisive using hierarchical significance testing and the Euclidean
distance-based divergence estimator.

[0]: https://arxiv.org/abs/1306.4933
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import itertools
import logging
import math
import random

from dashboard.common import math_utils

# TODO(dberris): Remove this dependency if/when we are able to depend on SciPy
# instead.
from dashboard.pinpoint.models.compare import compare as pinpoint_compare


class Error(Exception):
  pass


class InsufficientData(Error):
  pass


def Cluster(sequence, partition_point):
  """Return a tuple (left, right) where partition_point is part of right."""
  cluster_a = sequence[:partition_point]
  cluster_b = sequence[partition_point:]
  return (cluster_a, cluster_b)


def Midpoint(sequence):
  """Return an index in the sequence representing the midpoint."""
  return (len(sequence) - 1) // 2


def ClusterAndCompare(sequence, partition_point):
  """Returns the comparison result and the clusters at the partition point."""
  # Detect a difference between the two clusters
  cluster_a, cluster_b = Cluster(sequence, partition_point)
  if len(cluster_a) > 2 and len(cluster_b) > 2:
    magnitude = float(math_utils.Iqr(cluster_a) + math_utils.Iqr(cluster_b)) / 2
  else:
    magnitude = 1
  return (pinpoint_compare.Compare(cluster_a, cluster_b,
                                   (len(cluster_a) + len(cluster_b)) // 2,
                                   'performance',
                                   magnitude), cluster_a, cluster_b)


def PermutationTest(sequence, min_segment_size, rand=None):
  """Run permutation testing on a sequence.

  Determine whether there's a potential change point within the sequence,
  using randomised permutation testing.
  """
  if len(sequence) < (min_segment_size * 2) + 1:
    return False

  if rand is None:
    rand = random.Random()

  def RandomPermutations(sequence, length, count):
    pool = tuple(sequence)
    i = 0
    while i < count:
      i += 1
      yield tuple(rand.sample(pool, length))

  sames = 0
  differences = 0
  unknowns = 0
  for permutation in RandomPermutations(sequence, Midpoint(sequence),
                                        min(300,
                                            math.factorial(len(sequence)))):
    change_point, found = ChangePointEstimator(permutation, min_segment_size)
    if not found:
      sames += 1
      continue
    compare_result, unused_a, unused_b = ClusterAndCompare(
        permutation, change_point)
    if compare_result == pinpoint_compare.SAME:
      sames += 1
    elif compare_result == pinpoint_compare.UNKNOWN:
      unknowns += 1
    else:
      differences += 1

  # If at least 5% of the permutations compare differently, then it passes the
  # permutation test (meaning we can detect a potential change-point in the
  # sequence).
  logging.debug('sames = %s ; differences = %s ; unknowns = %s', sames,
                differences, unknowns)
  total = float(sames + unknowns + differences)
  probability = float(differences) / total if total > 0. else 0.
  logging.debug('Computed probability: %s for sequence %s', probability,
                sequence)
  return probability >= 0.05


def ChangePointEstimator(sequence, min_segment_size):
  # This algorithm does the following:
  #   - For each element in the sequence:
  #     - Partition the sequence into two clusters (X[a], X[b])
  #     - Compute the intra-cluster distances squared (X[n])
  #     - Scale the intra-cluster distances by the number of intra-cluster
  #       pairs. (X'[n] = X[n] / combinations(|X[n]|, 2) )
  #     - Compute the inter-cluster distances squared (Y)
  #     - Scale the inter-cluster distances by the number of total pairs
  #       multiplied by 2 (Y' = (Y * 2) / |X[a]||X[b]|)
  #     - Sum up as: Y' - X'[a] - X'[b]
  #   - Return the index of the highest estimator.
  #
  # The computation is based on Euclidean distances between measurements
  # within and across clusters to show the likelihood that the values on
  # either side of a sequence is likely to show a divergence.
  #
  # This algorithm is O(N^2) to the size of the sequence.
  def Estimator(index):
    cluster_a, cluster_b = Cluster(sequence, index)
    x_a = sum(abs(a - b)**2 for a, b in itertools.product(cluster_a, repeat=2))
    x_b = sum(abs(a - b)**2 for a, b in itertools.product(cluster_b, repeat=2))
    y = sum(abs(a - b)**2 for a, b in itertools.product(cluster_a, cluster_b))
    a_len_combinations = (
        math.factorial(len(cluster_a)) /
        (math.factorial(2) * math.factorial(len(cluster_a) - 1)))
    b_len_combinations = (
        math.factorial(len(cluster_b)) /
        (math.factorial(2) * math.factorial(len(cluster_b) - 1)))
    return (((y * 2.0) / (len(cluster_a) * len(cluster_b))) -
            (x_a / a_len_combinations) - (x_b / b_len_combinations))

  margin = max(min_segment_size, 1)
  estimates = [
      Estimator(i)
      for i, _ in enumerate(sequence)
      if margin <= i < len(sequence) - margin
  ]
  if not estimates:
    return (0, False)
  max_estimate = None
  max_index = 0
  for index, estimate in enumerate(estimates):
    if max_estimate is None or estimate > max_estimate:
      max_estimate = estimate
      max_index = index
  return (max_index + min_segment_size, True)


def ClusterAndFindSplit(values, min_segment_size, rand=None):
  """Finds a list of indices where we can detect significant changes.

  This algorithm looks for the point at which clusterings of the "left" and
  "right" datapoints show a significant difference. We understand that this
  algorithm is working on potentially already-aggregated data (means, etc.) and
  it would work better if we had access to all the underlying data points, but
  for now we can do our best with the points we have access to.

  In the E-Divisive paper, this is a two-step process: first estimate potential
  change points, then test whether the clusters partitioned by the proposed
  change point internally has potentially hidden change-points through random
  permutation testing. Because the current implementation only returns a single
  change-point, we do the change point estimation through bisection, and use the
  permutation testing to identify whether we should continue the bisection, not
  to find all potential change points.

  Arguments:
    - values: a sequence of values in time series order.
    - min_segment_size: the shortest segment of values to consider for
      refinement -- this allows callers to control the minimum size of segments
      to consider for finding potential change points.
    - rand: a callable which produces a value used for subsequence permutation
      testing.

  Returns:
    - A list of indices into values where we can detect potential split points.

  Raises:
    - InsufficientData when the algorithm cannot find potential change points
      with statistical significance testing.
  """

  logging.debug('Starting change point detection.')
  length = len(values)
  if length <= min_segment_size:
    raise InsufficientData(
        'Sequence is not larger than min_segment_size (%s <= %s)' %
        (length, min_segment_size))
  start = 0
  candidate_indices = []
  while True:
    # Find the most likely change point in the whole range, only excluding the
    # first and last elements. We're doing this because we want to still be able
    # to pick a candidate within the margins (of min_segment_size) if we have
    # enough confidence that it is a change point.
    partition_point, _ = ChangePointEstimator(values[start:start + length], 1)
    logging.debug('Values for start = %s, length = %s, partition_point = %s',
                  start, length, partition_point)

    # Compare the left and right part divided by the possible change point
    compare_result, cluster_a, cluster_b = ClusterAndCompare(
        values[start:start + length], partition_point)
    if compare_result == pinpoint_compare.DIFFERENT:
      candidate_indices.append(start + partition_point)

    in_a = False
    in_b = False

    # Even though we have a likely partiion point, we want to be able to find
    # other potential change points in the A and B clusters by performing
    # permutation testing to see potentially hidden change points.
    if len(cluster_a) > min_segment_size and PermutationTest(
        cluster_a, min_segment_size, rand):
      _, in_a = ChangePointEstimator(cluster_a, min_segment_size)

    if len(cluster_b) > min_segment_size and PermutationTest(
        cluster_b, min_segment_size, rand):
      _, in_b = ChangePointEstimator(cluster_b, min_segment_size)

    # Case 1: We haven't found alternative likely change points in either
    # cluster.
    if not in_a and not in_b:
      if not candidate_indices:
        raise InsufficientData('Not enough data to suggest a change point.')
      break

    # Case 2: We've found a likely change point in one of the clusters. In this
    # implementation we're biased towards finding the change points in the A
    # cluster (those earlier in time).
    # TODO(crbug/1045595): Change this to explore both clusters, using an
    # interval tree traversal algorithm.
    if in_a:
      length = min(partition_point + min_segment_size, len(values))
    elif in_b:
      length = min(len(cluster_b) + min_segment_size - 1, len(values))
      start += max(partition_point - (min_segment_size - 1), 0)

  return candidate_indices
