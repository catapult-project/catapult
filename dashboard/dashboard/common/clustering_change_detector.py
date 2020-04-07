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

import array
import itertools
import logging
import math
import random

from dashboard.common import math_utils

# TODO(dberris): Remove this dependency if/when we are able to depend on SciPy
# instead.
from dashboard.pinpoint.models.compare import compare as pinpoint_compare

# This number controls the maximum number of iterations we perform when doing
# permutation testing to identify potential change-points hidden in the
# sub-clustering of values. The higher the number, the more CPU time we're
# likely to spend finding these potential hidden change-points.
_MAX_PERMUTATION_TESTING_ITERATIONS = 150

class Error(Exception):
  pass


class InsufficientData(Error):
  pass


def Cluster(sequence, partition_point):
  """Return a tuple (left, right) where partition_point is part of right."""
  cluster_a = array.array('d', sequence[:partition_point])
  cluster_b = array.array('d', sequence[partition_point:])
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


def PermutationTest(sequence, rand=None):
  """Run permutation testing on a sequence.

  Determine whether there's a potential change point within the sequence,
  using randomised permutation testing.

  Arguments:
    - sequence: an iterable of values to perform permutation testing on.
    - rand: an implementation of a pseudo-random generator (see random.Random))

  Returns 'True' if there's a greater than 5% probability that a permutation of
  the values in the sequence, in a re-clustering contains a change-point.
  """
  if len(sequence) < 3:
    return False

  if rand is None:
    rand = random.Random()

  def RandomPermutations(sequence, length, count):
    pool = array.array('d', sequence)
    i = 0
    while i < count:
      i += 1
      yield array.array('d', rand.sample(pool, length))

  sames = 0
  differences = 0
  unknowns = 0
  for permutation in RandomPermutations(
      sequence, Midpoint(sequence),
      min(_MAX_PERMUTATION_TESTING_ITERATIONS, math.factorial(len(sequence)))):
    change_point, found = ChangePointEstimator(permutation)
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
  total = float(sames + unknowns + differences)
  probability = float(differences) / total if total > 0. else 0.
  logging.debug(
      'Computed probability: %s; sames = %s, differences = %s, unknowns = %s',
      probability, sames, differences, unknowns)
  return probability >= 0.05


def ChangePointEstimator(sequence):
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

  margin = 1
  estimates = array.array('d', (Estimator(i)
                                for i, _ in enumerate(sequence)
                                if margin <= i < len(sequence) - margin))
  if not estimates:
    return (0, False)
  max_estimate = None
  max_index = 0
  for index, estimate in enumerate(estimates):
    if max_estimate is None or estimate > max_estimate:
      max_estimate = estimate
      max_index = index
  return (max_index + margin, True)


def ClusterAndFindSplit(values, rand=None):
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
  if length <= 3:
    raise InsufficientData(
        'Sequence is not larger than minimum length (%s <= %s)' %
        (length, 3))
  start = 0
  candidate_indices = []
  while True:
    # Find the most likely change point in the whole range, only excluding the
    # first and last elements. We're doing this because we want to still be able
    # to pick a candidate within the margins (excluding the ends) if we have
    # enough confidence that it is a change point.
    segment = array.array('d', values[start:(start + length)])
    partition_point, _ = ChangePointEstimator(segment)
    logging.debug('Values for start = %s, length = %s, partition_point = %s',
                  start, length, partition_point)

    # Compare the left and right part divided by the possible change point
    compare_result, cluster_a, cluster_b = ClusterAndCompare(
        segment, partition_point)
    if compare_result == pinpoint_compare.DIFFERENT:
      candidate_indices.append(start + partition_point)

    in_a = False
    in_b = False

    # Even though we have a likely partiion point, we want to be able to find
    # other potential change points in the A and B clusters by performing
    # permutation testing to see potentially hidden change points.
    if PermutationTest(cluster_a, rand):
      logging.debug('A: Permutation testing positive at seq[%s:%s]', start,
                    partition_point)
      _, in_a = ChangePointEstimator(cluster_a)

    if PermutationTest(cluster_b, rand):
      logging.debug('B: Permutation testing positive at seq[%s:%s]',
                    start + partition_point, length)
      _, in_b = ChangePointEstimator(cluster_b)

    # Case 1: We haven't found alternative likely change points in either
    # cluster.
    if not in_a and not in_b:
      break

    # Case 2: We've found a likely change point in one of the clusters. In this
    # implementation we're biased towards finding the change points in the A
    # cluster (those earlier in time).
    # TODO(crbug/1045595): Change this to explore both clusters, using an
    # interval tree traversal algorithm.
    if in_a:
      new_length = min(partition_point + 1, length)
      logging.debug('New length: %d', new_length)
      length = new_length
    elif in_b:
      new_length = min(len(cluster_b), length)
      new_start = start + max(partition_point, 0)
      logging.debug('New start: %d ; new_length: %d', new_start, new_length)
      start, length = new_start, new_length

  if not candidate_indices:
    raise InsufficientData('Not enough data to suggest a change point.')
  return candidate_indices
