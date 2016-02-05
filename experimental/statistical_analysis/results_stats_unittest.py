#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for results_stats."""

import os
import sys

import unittest

try:
  import numpy as np
except ImportError:
  np = None

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from statistical_analysis import results_stats


class StatisticalBenchmarkResultsAnalysisTest(unittest.TestCase):
  """Unit testing of several functions in results_stats."""

  def testCreateBenchmarkResultDictFromJson(self):
    """Unit test for benchmark results dict created from a benchmark json.

    Creates a json of the format created by tools/perf/run_benchmark (currently
    for startup benchmarks only) and then compares the output dict against an
    expected predefined output dict.
    """
    input_json_wrong_format = {'charts_wrong': {}}
    with self.assertRaises(ValueError):
      (results_stats.
       CreateBenchmarkResultDictFromJson(input_json_wrong_format))

    measurement_names = ['messageloop_start_time',
                         'open_tabs_time',
                         'window_display_time']
    measurement_values = [[55, 72, 60], [54, 42, 65], [44, 89]]

    input_json = {'charts': {}}
    for name, vals in zip(measurement_names, measurement_values):
      input_json['charts'][name] = {'summary': {'values': vals}}

    output = (results_stats.CreateBenchmarkResultDictFromJson(input_json))
    expected_output = {'messageloop_start_time':
                       [55, 72, 60],
                       'open_tabs_time':
                       [54, 42, 65],
                       'window_display_time':
                       [44, 89]}

    self.assertEqual(output, expected_output)

  def testMergeTwoBenchmarkResultDicts(self):
    """Unit test for merged result dict created from two benchmark dicts.

    Creates two dicts containing the same three metrics and compares the output
    dict against an expected predefined output dict. Also checks if exception
    is raised for mismatching dicts.
    """
    input_dict_1 = {'messageloop_start_time': [55, 72, 60],
                    'open_tabs_time': [54, 42, 65],
                    'window_display_time': [44, 89]}
    input_dict_2 = {'messageloop_start_time': [110, 144, 90],
                    'window_display_time': [88, 178],
                    'open_tabs_time': [108, 84, 130]}

    input_dict_mismatch = {'messageloop_start_time': [55, 72, 60],
                           'first_main_frame_load_time': [54, 42, 65],
                           'window_display_time': [44, 89]}

    with self.assertRaises(results_stats.DictMismatchError):
      results_stats.MergeTwoBenchmarkResultDicts(input_dict_1,
                                                 input_dict_mismatch)

    output = results_stats.MergeTwoBenchmarkResultDicts(input_dict_1,
                                                        input_dict_2)
    expected_output = {'messageloop_start_time': ([55, 72, 60],
                                                  [110, 144, 90]),
                       'window_display_time': ([44, 89], [88, 178]),
                       'open_tabs_time': ([54, 42, 65], [108, 84, 130])}

    self.assertEqual(output, expected_output)

  def CreateRandomNormalDistributions(self):
    """Creates two pseudo random samples for testing in multiple methods."""
    if not np:
      raise ImportError('This function requires Numpy.')

    np.random.seed(0)
    sample_1 = np.random.normal(loc=0, scale=1, size=30)
    sample_2 = np.random.normal(loc=1, scale=1, size=30)

    return [sample_1, sample_2]

  def testIsNormallyDistributed(self):
    """Unit test for values returned when testing for normality."""
    if not np:
      self.skipTest("Numpy is not installed.")

    test_samples = self.CreateRandomNormalDistributions()

    expected_output = [(True, 0.5253966450691223),
                       (True, 0.9084850549697876)]
    for i in range(len(test_samples)):
      output = (results_stats.IsNormallyDistributed(test_samples[i],
                                                    return_p_value=True))

      self.assertEqual(output, expected_output[i])

  def testIsSignificantlyDifferent(self):
    """Unit test for values returned after running the statistical tests.

    Creates two pseudo-random normally distributed samples to run the
    statistical tests and compares the resulting answer and p-value against
    their pre-calculated values.
    """
    if not np:
      self.skipTest("Numpy is not installed.")

    test_samples = self.CreateRandomNormalDistributions()
    test_options = [(results_stats.MANN),
                    (results_stats.KOLMOGOROV),
                    (results_stats.WELCH)]

    expected_output = [(False, 2*0.23667327862922477),
                       (True, 0.34203417981555007),
                       (True, 0.30993097798453401)]

    for i in range(len(test_options)):
      output = (results_stats.IsSignificantlyDifferent(test_samples[0],
                                                       test_samples[1],
                                                       test=test_options[i],
                                                       significance_level=0.35,
                                                       return_p_value=True))
      self.assertEqual(output, expected_output[i])


if __name__ == '__main__':
  sys.exit(unittest.main())
