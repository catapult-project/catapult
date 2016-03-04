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


def PrintOutcomeLine(name, max_name_length, outcome, print_p_value):
  """Prints a single output line, e.g. 'metric_1  True  0.03'."""
  print('{:{}}{}'.format(name, max_name_length + 2, outcome[0]), end='')
  if print_p_value:
    print('\t{:.10f}'.format(outcome[1]), end='')
  print()


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

  max_metric_name_len = max([len(metric_name) for metric_name in
                             test_outcome_dict])

  for metric_name, outcome in test_outcome_dict.iteritems():
    PrintOutcomeLine(metric_name, max_metric_name_len, outcome, print_p_value)


def PrintPagesetTestOutcome(test_outcome_dict, test_name, significance_level,
                            print_p_value, print_details):
  """Prints the given test outcomes to the command line.

  Prints a summary combining the p-values of the pageset for each metric. Then
  prints results for each metric/page combination if |print_details| is True.
  """
  print('Statistical analysis results (True=Performance difference likely)\n'
        '(Test: {}, Significance Level: {})\n'.format(test_name,
                                                      significance_level))

  # Print summarized version at the top.
  max_metric_name_len = max([len(metric_name) for metric_name in
                             test_outcome_dict])
  print('Summary (combined p-values for all pages in pageset):\n')
  for metric_name, pageset in test_outcome_dict.iteritems():
    combined_p_value = results_stats.CombinePValues([p[1] for p in
                                                     pageset.itervalues()])
    outcome = (combined_p_value < significance_level, combined_p_value)
    PrintOutcomeLine(metric_name, max_metric_name_len, outcome, print_p_value)
  print()

  if not print_details:
    return

  # Print outcome for every metric/page combination.
  for metric_name, pageset in test_outcome_dict.iteritems():
    max_page_name_len = max([len(page_name) for page_name in pageset])
    print('{}:'.format(metric_name))
    for page_name, page_outcome in pageset.iteritems():
      PrintOutcomeLine(page_name, max_page_name_len, page_outcome,
                       print_p_value)
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

  parser.add_argument('-d', action='store_true', dest='print_details',
                      help="""If the -d flag is set, the output will be more
                      detailed for benchmarks containing pagesets, giving
                      results for every metric/page combination after a summary
                      at the top.""")

  args = parser.parse_args(args)

  result_jsons = [LoadJsonFromPath(json_path) for json_path in args.json_paths]

  if (results_stats.DoesChartJSONContainPageset(result_jsons[0]) and
      results_stats.DoesChartJSONContainPageset(result_jsons[1])):
    # Benchmark containing a pageset.
    result_dict_1, result_dict_2 = (
        [results_stats.CreatePagesetBenchmarkResultDict(result_json)
         for result_json in result_jsons])
    test_outcome_dict = results_stats.ArePagesetBenchmarkResultsDifferent(
        result_dict_1, result_dict_2, args.statistical_test,
        args.significance_level)

    PrintPagesetTestOutcome(test_outcome_dict, args.statistical_test,
                            args.significance_level, args.print_p_value,
                            args.print_details)

  else:
    # Benchmark not containing a pageset.
    # (If only one JSON contains a pageset, results_stats raises an error.)
    result_dict_1, result_dict_2 = (
        [results_stats.CreateBenchmarkResultDict(result_json)
         for result_json in result_jsons])
    test_outcome_dict = (
        results_stats.AreBenchmarkResultsDifferent(result_dict_1, result_dict_2,
                                                   args.statistical_test,
                                                   args.significance_level))

    PrintTestOutcome(test_outcome_dict, args.statistical_test,
                     args.significance_level, args.print_p_value)


if __name__ == '__main__':
  sys.exit(main())
