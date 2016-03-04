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

  def testGetChartsFromBenchmarkResultJson(self):
    """Unit test for errors raised when getting the charts element.

    Also makes sure that the 'trace' element is deleted if it exists.
    """
    input_json_wrong_format = {'charts_wrong': {}}
    input_json_empty = {'charts': {}}
    with self.assertRaises(ValueError):
      (results_stats.GetChartsFromBenchmarkResultJson(input_json_wrong_format))
    with self.assertRaises(ValueError):
      (results_stats.GetChartsFromBenchmarkResultJson(input_json_empty))

    input_json_with_trace = {'charts':
                             {'trace': {},
                              'Ex_metric_1':
                              {'Ex_page_1': {'type': 'list_of_scalar_values',
                                             'values': [1, 2]},
                               'Ex_page_2': {'type': 'histogram',
                                             'values': [1, 2]}},
                              'Ex_metric_2':
                              {'Ex_page_1': {'type': 'list_of_scalar_values'},
                               'Ex_page_2': {'type': 'list_of_scalar_values',
                                             'values': [1, 2]}}}}

    output = (results_stats.
              GetChartsFromBenchmarkResultJson(input_json_with_trace))
    expected_output = {'Ex_metric_1':
                       {'Ex_page_1': {'type': 'list_of_scalar_values',
                                      'values': [1, 2]}},
                       'Ex_metric_2':
                       {'Ex_page_2': {'type': 'list_of_scalar_values',
                                      'values': [1, 2]}}}
    self.assertEqual(output, expected_output)

  def testCreateBenchmarkResultDict(self):
    """Unit test for benchmark result dict created from a benchmark json.

    Creates a json of the format created by tools/perf/run_benchmark and then
    compares the output dict against an expected predefined output dict.
    """
    metric_names = ['messageloop_start_time',
                    'open_tabs_time',
                    'window_display_time']
    metric_values = [[55, 72, 60], [54, 42, 65], [44, 89]]

    input_json = {'charts': {}}
    for metric, metric_vals in zip(metric_names, metric_values):
      input_json['charts'][metric] = {'summary':
                                      {'values': metric_vals,
                                       'type': 'list_of_scalar_values'}}

    output = results_stats.CreateBenchmarkResultDict(input_json)
    expected_output = {'messageloop_start_time': [55, 72, 60],
                       'open_tabs_time': [54, 42, 65],
                       'window_display_time': [44, 89]}

    self.assertEqual(output, expected_output)

  def testCreatePagesetBenchmarkResultDict(self):
    """Unit test for pageset benchmark result dict created from benchmark json.

    Creates a json of the format created by tools/perf/run_benchmark when it
    includes a pageset and then compares the output dict against an expected
    predefined output dict.
    """
    metric_names = ['messageloop_start_time',
                    'open_tabs_time',
                    'window_display_time']
    metric_values = [[55, 72, 60], [54, 42, 65], [44, 89]]
    page_names = ['Ex_page_1', 'Ex_page_2']

    input_json = {'charts': {}}
    for metric, metric_vals in zip(metric_names, metric_values):
      input_json['charts'][metric] = {'summary':
                                      {'values': [0, 1, 2, 3],
                                       'type': 'list_of_scalar_values'}}
      for page in page_names:
        input_json['charts'][metric][page] = {'values': metric_vals,
                                              'type': 'list_of_scalar_values'}

    output = results_stats.CreatePagesetBenchmarkResultDict(input_json)
    expected_output = {'messageloop_start_time': {'Ex_page_1': [55, 72, 60],
                                                  'Ex_page_2': [55, 72, 60]},
                       'open_tabs_time': {'Ex_page_1': [54, 42, 65],
                                          'Ex_page_2': [54, 42, 65]},
                       'window_display_time': {'Ex_page_1': [44, 89],
                                               'Ex_page_2': [44, 89]}}

    self.assertEqual(output, expected_output)

  def testCombinePValues(self):
    """Unit test for Fisher's Method that combines multiple p-values."""
    test_p_values = [0.05, 0.04, 0.10, 0.07, 0.01]

    expected_output = 0.00047334256271885721
    output = results_stats.CombinePValues(test_p_values)

    self.assertEqual(output, expected_output)

  def CreateRandomNormalDistribution(self, mean=0, size=30):
    """Creates two pseudo random samples for testing in multiple methods."""
    if not np:
      raise ImportError('This function requires Numpy.')

    np.random.seed(0)
    sample = np.random.normal(loc=mean, scale=1, size=size)

    return sample

  def testIsNormallyDistributed(self):
    """Unit test for values returned when testing for normality."""
    if not np:
      self.skipTest("Numpy is not installed.")

    test_samples = [self.CreateRandomNormalDistribution(0),
                    self.CreateRandomNormalDistribution(1)]

    expected_outputs = [(True, 0.5253966450691223),
                        (True, 0.5253913402557373)]
    for sample, expected_output in zip(test_samples, expected_outputs):
      output = results_stats.IsNormallyDistributed(sample)

      self.assertEqual(output, expected_output)

  def testAreSamplesDifferent(self):
    """Unit test for values returned after running the statistical tests.

    Creates two pseudo-random normally distributed samples to run the
    statistical tests and compares the resulting answer and p-value against
    their pre-calculated values.
    """
    test_samples = [3 * [0, 0, 2, 4, 4], 3 * [5, 5, 7, 9, 9]]
    with self.assertRaises(results_stats.SampleSizeError):
      results_stats.AreSamplesDifferent(test_samples[0], test_samples[1],
                                        test=results_stats.MANN)
    with self.assertRaises(results_stats.NonNormalSampleError):
      results_stats.AreSamplesDifferent(test_samples[0], test_samples[1],
                                        test=results_stats.WELCH)

    test_samples_equal = (20 * [1], 20 * [1])
    expected_output_equal = (False, 1.0)
    output_equal = results_stats.AreSamplesDifferent(test_samples_equal[0],
                                                     test_samples_equal[1],
                                                     test=results_stats.MANN)
    self.assertEqual(output_equal, expected_output_equal)

    if not np:
      self.skipTest("Numpy is not installed.")

    test_samples = [self.CreateRandomNormalDistribution(0),
                    self.CreateRandomNormalDistribution(1)]
    test_options = results_stats.ALL_TEST_OPTIONS

    expected_outputs = [(True, 2 * 0.00068516628052438266),
                        (True, 0.0017459498829507842),
                        (True, 0.00084765230478226514)]

    for test, expected_output in zip(test_options, expected_outputs):
      output = results_stats.AreSamplesDifferent(test_samples[0],
                                                 test_samples[1],
                                                 test=test)
      self.assertEqual(output, expected_output)

  def testAssertThatKeysMatch(self):
    """Unit test for exception raised when input dicts' metrics don't match."""
    differing_input_dicts = [{'messageloop_start_time': [55, 72, 60],
                              'display_time': [44, 89]},
                             {'messageloop_start_time': [55, 72, 60]}]
    with self.assertRaises(results_stats.DictMismatchError):
      results_stats.AssertThatKeysMatch(differing_input_dicts[0],
                                        differing_input_dicts[1])

  def testAreBenchmarkResultsDifferent(self):
    """Unit test for statistical test outcome dict."""
    test_input_dicts = [{'open_tabs_time':
                         self.CreateRandomNormalDistribution(0),
                         'display_time':
                         self.CreateRandomNormalDistribution(0)},
                        {'open_tabs_time':
                         self.CreateRandomNormalDistribution(0),
                         'display_time':
                         self.CreateRandomNormalDistribution(1)}]
    test_options = results_stats.ALL_TEST_OPTIONS

    expected_outputs = [{'open_tabs_time': (False, 2 * 0.49704973080841425),
                         'display_time': (True, 2 * 0.00068516628052438266)},
                        {'open_tabs_time': (False, 1.0),
                         'display_time': (True, 0.0017459498829507842)},
                        {'open_tabs_time': (False, 1.0),
                         'display_time': (True, 0.00084765230478226514)}]

    for test, expected_output in zip(test_options, expected_outputs):
      output = results_stats.AreBenchmarkResultsDifferent(test_input_dicts[0],
                                                          test_input_dicts[1],
                                                          test=test)
      self.assertEqual(output, expected_output)

  def testArePagesetBenchmarkResultsDifferent(self):
    """Unit test for statistical test outcome dict."""
    distributions = (self.CreateRandomNormalDistribution(0),
                     self.CreateRandomNormalDistribution(1))
    test_input_dicts = ({'open_tabs_time': {'Ex_page_1': distributions[0],
                                            'Ex_page_2': distributions[0]},
                         'display_time': {'Ex_page_1': distributions[1],
                                          'Ex_page_2': distributions[1]}},
                        {'open_tabs_time': {'Ex_page_1': distributions[0],
                                            'Ex_page_2': distributions[1]},
                         'display_time': {'Ex_page_1': distributions[1],
                                          'Ex_page_2': distributions[0]}})
    test_options = results_stats.ALL_TEST_OPTIONS

    expected_outputs = ({'open_tabs_time':  # Mann.
                         {'Ex_page_1': (False, 2 * 0.49704973080841425),
                          'Ex_page_2': (True, 2 * 0.00068516628052438266)},
                         'display_time':
                         {'Ex_page_1': (False, 2 * 0.49704973080841425),
                          'Ex_page_2': (True, 2 * 0.00068516628052438266)}},
                        {'open_tabs_time':  # Kolmogorov.
                         {'Ex_page_1': (False, 1.0),
                          'Ex_page_2': (True, 0.0017459498829507842)},
                         'display_time':
                         {'Ex_page_1': (False, 1.0),
                          'Ex_page_2': (True, 0.0017459498829507842)}},
                        {'open_tabs_time':  # Welch.
                         {'Ex_page_1': (False, 1.0),
                          'Ex_page_2': (True, 0.00084765230478226514)},
                         'display_time':
                         {'Ex_page_1': (False, 1.0),
                          'Ex_page_2': (True, 0.00084765230478226514)}})

    for test, expected_output in zip(test_options, expected_outputs):
      output = (results_stats.
                ArePagesetBenchmarkResultsDifferent(test_input_dicts[0],
                                                    test_input_dicts[1],
                                                    test=test))
      self.assertEqual(output, expected_output)


if __name__ == '__main__':
  sys.exit(unittest.main())
