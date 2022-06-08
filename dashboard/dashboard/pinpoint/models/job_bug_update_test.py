# Copyright 2022 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.models import anomaly
from dashboard.pinpoint.models import job_bug_update
from dashboard.pinpoint import test


class OrderedDifferenceTest(test.TestCase):

  def testOrderedDifference(self):
    # populate differences
    d = job_bug_update.DifferencesFoundBugUpdateBuilder(metric='metric')
    kind = 'commit'
    commit_dict = {}

    values_a = [0]
    values_b = [1]
    d._differences.append(
        job_bug_update._Difference(kind, commit_dict, values_a, values_b))
    values_a = [0]
    values_b = [-2]
    d._differences.append(
        job_bug_update._Difference(kind, commit_dict, values_a, values_b))
    values_a = [0]
    values_b = [3]
    d._differences.append(
        job_bug_update._Difference(kind, commit_dict, values_a, values_b))

    # check improvement direction UP
    ordered_diff = d._OrderedDifferencesByDelta(anomaly.UP)
    self.assertEqual(ordered_diff[0].MeanDelta(), -2)
    self.assertEqual(ordered_diff[1].MeanDelta(), 1)
    self.assertEqual(ordered_diff[2].MeanDelta(), 3)

    # check improvement direction DOWN
    d._cached_ordered_diffs_by_delta = None  # reset cache
    ordered_diff = d._OrderedDifferencesByDelta(anomaly.DOWN)
    self.assertEqual(ordered_diff[0].MeanDelta(), 3)
    self.assertEqual(ordered_diff[1].MeanDelta(), 1)
    self.assertEqual(ordered_diff[2].MeanDelta(), -2)

    # check improvement direction UNKNOWN
    d._cached_ordered_diffs_by_delta = None  # reset cache
    ordered_diff = d._OrderedDifferencesByDelta(anomaly.UNKNOWN)
    self.assertEqual(ordered_diff[0].MeanDelta(), 3)
    self.assertEqual(ordered_diff[1].MeanDelta(), -2)
    self.assertEqual(ordered_diff[2].MeanDelta(), 1)
