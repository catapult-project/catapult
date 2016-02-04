# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Statistical hypothesis testing for comparing benchmark results."""

try:
  from scipy import stats
except ImportError:
  stats = None


MANN = 'mann'
KOLMOGOROV = 'kolmogorov'
WELCH = 'welch'


class DictMismatchError(Exception):
  """Provides exception for result dicts with mismatching keys/metrics."""
  def __str__(self):
    return ("Provided benchmark result dicts' keys/metrics do not match. "
            "Check if they have been created by the same benchmark.")


def CreateBenchmarkResultDictFromJson(benchmark_result_json):
  """Creates a dict of format {measure_name: list of benchmark results}.

  Takes a raw result Chart-JSON produced when using '--output-format=chartjson'
  when running 'run_benchmark'.

  Args:
    benchmark_result_json: Benchmark result Chart-JSON produced by Telemetry.

  Returns:
    Dictionary of benchmark results.
    Example dict entry: 'first_main_frame_load_time': [650, 700, ...].
  """
  try:
    charts = benchmark_result_json['charts']
  except KeyError:
    raise ValueError('Invalid benchmark result format. Make sure input is a '
                     'Chart-JSON.\nProvided JSON:\n',
                     repr(benchmark_result_json))

  benchmark_result_dict = {}
  for elem_name, elem_content in charts.iteritems():
    benchmark_result_dict[elem_name] = elem_content['summary']['values']

  return benchmark_result_dict


def MergeTwoBenchmarkResultDicts(benchmark_result_dict_1,
                                 benchmark_result_dict_2):
  """Merges two benchmark result dicts into a single dict.

  Also checks if the dicts have been created from the same benchmark, i.e. if
  measurement names match.

  Args:
    benchmark_result_dict_1: dict of format {metric: list of values}.
    benchmark_result_dict_2: dict of format {metric: list of values}.

  Returns:
    Dict of format {metric: (list of values 1, list of values 2)}.
  """
  if benchmark_result_dict_1.viewkeys() != benchmark_result_dict_2.viewkeys():
    raise DictMismatchError()

  merged_dict = {}
  for measurement in benchmark_result_dict_1:
    merged_dict[measurement] = (benchmark_result_dict_1[measurement],
                                benchmark_result_dict_2[measurement])

  return merged_dict


def IsNormallyDistributed(sample, significance_level=0.05,
                          return_p_value=False):
  """Calculates Shapiro-Wilk test for normality.

  Note that normality is a requirement for Welch's t-test.

  Args:
    sample: List of values of benchmark result for a measure.
    significance_level: The significance level the p-value is compared against.
    return_p_value: Whether or not to return the calculated p-value.

  Returns:
    is_normally_distributed: Returns True or False.
    p_value: The calculated p-value.
  """
  if not stats:
    raise ImportError('This function requires Scipy.')

  # pylint: disable=unbalanced-tuple-unpacking
  _, p_value = stats.shapiro(sample)

  is_normally_distributed = p_value >= significance_level
  if return_p_value:
    return is_normally_distributed, p_value
  return is_normally_distributed


def IsSignificantlyDifferent(sample_1, sample_2, test=MANN,
                             significance_level=0.05, return_p_value=False):
  """Calculates the specified statistical test for the given benchmark results.

  The null hypothesis for each test is that the two results are not
  significantly different.

  Args:
    sample_1: List of values of first benchmark result.
    sample_2: List of values of second benchmark result.
    test: Statistical test that is used.
    significance_level: The significance level the p-value is compared against.
    return_p_value: Whether or not to return the calculated p-value.

  Returns:
    is_different: True or False, depending on test outcome.
    p_value: The p-value the test has produced.
  """
  if not stats:
    raise ImportError('This function requires Scipy.')

  if test == MANN:
    if len(sample_1) < 20 or len(sample_2) < 20:
      print('Warning: At least one sample size is smaller than 20, so '
            'Mann-Whitney U-test might be inaccurate. Consider increasing '
            'sample size or picking a different test.')
    _, p_value = stats.mannwhitneyu(sample_1, sample_2, use_continuity=True)
    # Returns a one-sided p-value, so multiply result by 2 for a two-sided
    # p-value.
    p_value = p_value * 2 if p_value < 0.5 else 1
  elif test == KOLMOGOROV:
    _, p_value = stats.ks_2samp(sample_1, sample_2)
  elif test == WELCH:
    _, p_value = stats.ttest_ind(sample_1, sample_2, equal_var=False)
  # TODO: Add k sample anderson darling test

  is_different = p_value <= significance_level
  if return_p_value:
    return is_different, p_value
  return is_different
