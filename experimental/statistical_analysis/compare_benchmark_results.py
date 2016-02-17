#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Calculates statistical hypothesis test for given benchmark results.

Evaluate two benchmark results given as Chart JSON files to determine how
statistically significantly different they are. This evaluation should be run
using Chart JSON files created by one of the available benchmarks in
tools/perf/run_benchmark.

A "benchmark" (e.g. startup.cold.blank_page) includes several "metrics" (e.g.
first_main_frame_load_time).
"""

from __future__ import print_function
import argparse
import json
import os
import sys

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..')))
from statistical_analysis import results_stats


DEFAULT_SIGNIFICANCE_LEVEL = 0.05
DEFAULT_STATISTICAL_TEST = results_stats.MANN


def LoadJsonFromPath(json_path):
  """Returns a JSON from specified location."""
  with open(os.path.abspath(json_path)) as data_file:
    return json.load(data_file)


def PrintTestOutcome(test_outcome_dict, test_name, significance_level,
                     print_p_value):
  """Prints the given test outcomes to the command line.

  Will print the p-values for each metric's outcome if |print_p_value| is True
  and also prints the name of the executed statistical test and the
  significance level.
  """
  print('Statistical analysis results (True=Performance difference likely)\n'
        '(Test: {}, Significance Level: {})\n'.format(test_name,
                                                      significance_level))

  max_metric_name_length = max([len(metric_name) for metric_name in
                                test_outcome_dict])

  for metric, outcome in test_outcome_dict.iteritems():
    print('{:{}}{}'.format(metric, max_metric_name_length + 2, outcome[0]),
          end='')
    if print_p_value:
      print('\t{:05.3f}'.format(outcome[1]), end='')
    print()


def main(args=None):
  """Set up parser and run statistical test on given benchmark results.

  Set up command line parser and its arguments. Then load Chart JSONs from
  given paths, run the specified statistical hypothesis test on the results and
  print the test outcomes.
  """
  if args is None:
    args = sys.argv[1:]

  parser = argparse.ArgumentParser(description="""Runs statistical significance
                                   tests on two given Chart JSON benchmark
                                   results produced by the telemetry
                                   benchmarks.""")

  parser.add_argument(dest='json_paths', nargs=2, help='JSON file location')

  parser.add_argument('--significance', dest='significance_level',
                      default=DEFAULT_SIGNIFICANCE_LEVEL, type=float,
                      help="""The significance level is the type I error rate,
                      which is the probability of determining that the
                      benchmark results are different although they're not.
                      Default: {}, which is common in statistical hypothesis
                      testing.""".format(DEFAULT_SIGNIFICANCE_LEVEL))

  parser.add_argument('--statistical-test', dest='statistical_test',
                      default=DEFAULT_STATISTICAL_TEST,
                      choices=results_stats.ALL_TEST_OPTIONS,
                      help="""Specifies the statistical hypothesis test that is
                      used. Choices are: Mann-Whitney U-test,
                      Kolmogorov-Smirnov, Welch's t-test. Default: Mann-Whitney
                      U-Test.""")

  parser.add_argument('-p', action='store_true', dest='print_p_value',
                      help="""If the -p flag is set, the output will include
                      the p-value for each metric.""")

  args = parser.parse_args(args)

  result_dict_1, result_dict_2 = (
      [(results_stats.CreateBenchmarkResultDict(LoadJsonFromPath(json_path)))
       for json_path in args.json_paths])

  test_outcome_dict = (
      results_stats.AreBenchmarkResultsDifferent(result_dict_1, result_dict_2,
                                                 args.statistical_test,
                                                 args.significance_level))

  PrintTestOutcome(test_outcome_dict, args.statistical_test,
                   args.significance_level, args.print_p_value)


if __name__ == '__main__':
  sys.exit(main())
