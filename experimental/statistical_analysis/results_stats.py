# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Statistical hypothesis testing for comparing benchmark results."""

try:
  import numpy as np
except ImportError:
  np = None

try:
  from scipy import stats
  import scipy.version
except ImportError:
  stats = None


MANN = 'mann'
KOLMOGOROV = 'kolmogorov'
WELCH = 'welch'
ALL_TEST_OPTIONS = [MANN, KOLMOGOROV, WELCH]


class DictMismatchError(Exception):
  """Provides exception for result dicts with mismatching keys/metrics."""
  def __str__(self):
    return ("Provided benchmark result dicts' keys/metrics do not match. "
            "Check if they have been created by the same benchmark.")


class SampleSizeError(Exception):
  """Provides exception for sample sizes too small for Mann-Whitney U-test."""
  def __str__(self):
    return ('At least one sample size is smaller than 20, which is too small '
            'for Mann-Whitney U-test.')


class NonNormalSampleError(Exception):
  """Provides exception for samples that are not normally distributed."""
  def __str__(self):
    return ("At least one sample is not normally distributed as required by "
            "Welch's t-test.")


def IsScipyMannTestOneSided():
  """Checks if Scipy version is < 0.17.0.

  This is the version where stats.mannwhitneyu(...) is changed from returning
  a one-sided to returning a two-sided p-value.
  """
  scipy_version = [int(num) for num in scipy.version.version.split('.')]
  return scipy_version[0] < 1 and scipy_version[1] < 17


def GetChartsFromBenchmarkResultJson(benchmark_result_json):
  """Returns the 'charts' element from a given Chart JSON.

  Excludes entries that are not list_of_scalar_values and empty entries. Also
  raises errors for an invalid JSON format or empty 'charts' element.

  Raises:
    ValueError: Provided chart JSON is either not valid or 'charts' is empty.
  """
  try:
    charts = benchmark_result_json['charts']
  except KeyError:
    raise ValueError('Invalid benchmark result format. Make sure input is a '
                     'Chart-JSON.\nProvided JSON:\n',
                     repr(benchmark_result_json))
  if not charts:
    raise ValueError("Invalid benchmark result format. Dict entry 'charts' is "
                     "empty.")

  def IsValidPageContent(page_content):
    return (page_content['type'] == 'list_of_scalar_values' and
            'values' in page_content)

  def CreatePageDict(metric_content):
    return {page_name: page_content
            for page_name, page_content in metric_content.iteritems()
            if IsValidPageContent(page_content)}

  charts_valid_entries_only = {}
  for metric_name, metric_content in charts.iteritems():
    inner_page_dict = CreatePageDict(metric_content)
    if not inner_page_dict:
      continue
    charts_valid_entries_only[metric_name] = inner_page_dict

  return charts_valid_entries_only


def DoesChartJSONContainPageset(benchmark_result_json):
  """Checks if given Chart JSON contains results for a pageset.

  A metric in a benchmark NOT containing a pageset contains only two elements
  ("Only_page_in_this_benchmark" and "Summary", as opposed to "Ex_page_1",
  "Ex_page_2", ..., and "Summary").
  """
  charts = GetChartsFromBenchmarkResultJson(benchmark_result_json)

  arbitrary_metric_in_charts = charts.itervalues().next()
  return len(arbitrary_metric_in_charts) > 2


def CreateBenchmarkResultDict(benchmark_result_json):
  """Creates a dict of format {metric_name: list of benchmark results}.

  Takes a raw result Chart-JSON produced when using '--output-format=chartjson'
  for 'run_benchmark'.

  Args:
    benchmark_result_json: Benchmark result Chart-JSON produced by Telemetry.

  Returns:
    Dictionary of benchmark results.
    Example dict entry: 'tab_load_time': [650, 700, ...].
  """
  charts = GetChartsFromBenchmarkResultJson(benchmark_result_json)

  benchmark_result_dict = {}
  for metric_name, metric_content in charts.iteritems():
    benchmark_result_dict[metric_name] = metric_content['summary']['values']

  return benchmark_result_dict


def CreatePagesetBenchmarkResultDict(benchmark_result_json):
  """Creates a dict of format {metric_name: {page_name: list of page results}}.

  Takes a raw result Chart-JSON produced by 'run_benchmark' when using
  '--output-format=chartjson' and when specifying a benchmark that has a
  pageset (e.g. top25mobile). Run 'DoesChartJSONContainPageset' to check if
  your Chart-JSON contains a pageset.

  Args:
    benchmark_result_json: Benchmark result Chart-JSON produced by Telemetry.

  Returns:
    Dictionary of benchmark results.
    Example dict entry: 'tab_load_time': 'Gmail.com': [650, 700, ...].
  """
  charts = GetChartsFromBenchmarkResultJson(benchmark_result_json)

  benchmark_result_dict = {}
  for metric_name, metric_content in charts.iteritems():
    benchmark_result_dict[metric_name] = {}
    for page_name, page_content in metric_content.iteritems():
      if page_name == 'summary':
        continue
      benchmark_result_dict[metric_name][page_name] = page_content['values']

  return benchmark_result_dict


def CombinePValues(p_values):
  """Combines p-values from a number of tests using Fisher's Method.

  The tests the p-values result from must test the same null hypothesis and be
  independent.

  Args:
    p_values: List of p-values.

  Returns:
    combined_p_value: Combined p-value according to Fisher's method.
  """
  # TODO (wierichs): Update to use scipy.stats.combine_pvalues(p_values) when
  # Scipy v0.15.0 becomes available as standard version.
  if not np:
    raise ImportError('This function requires Numpy.')

  if not stats:
    raise ImportError('This function requires Scipy.')

  test_statistic = -2 * np.sum(np.log(p_values))
  p_value = stats.chi2.sf(test_statistic, 2 * len(p_values))
  return p_value


def IsNormallyDistributed(sample, significance_level=0.05):
  """Calculates Shapiro-Wilk test for normality for a single sample.

  Note that normality is a requirement for Welch's t-test.

  Args:
    sample: List of values.
    significance_level: The significance level the p-value is compared against.

  Returns:
    is_normally_distributed: Returns True or False.
    p_value: The calculated p-value.
  """
  if not stats:
    raise ImportError('This function requires Scipy.')

  # pylint: disable=unbalanced-tuple-unpacking
  _, p_value = stats.shapiro(sample)

  is_normally_distributed = p_value >= significance_level
  return is_normally_distributed, p_value


def AreSamplesDifferent(sample_1, sample_2, test=MANN,
                        significance_level=0.05):
  """Calculates the specified statistical test for the given samples.

  The null hypothesis for each test is that the two populations that the
  samples are taken from are not significantly different. Tests are two-tailed.

  Raises:
    ImportError: Scipy is not installed.
    SampleSizeError: Sample size is too small for MANN.
    NonNormalSampleError: Sample is not normally distributed as required by
    WELCH.

  Args:
    sample_1: First list of values.
    sample_2: Second list of values.
    test: Statistical test that is used.
    significance_level: The significance level the p-value is compared against.

  Returns:
    is_different: True or False, depending on the test outcome.
    p_value: The p-value the test has produced.
  """
  if not stats:
    raise ImportError('This function requires Scipy.')

  if test == MANN:
    if len(sample_1) < 20 or len(sample_2) < 20:
      raise SampleSizeError()
    try:
      _, p_value = stats.mannwhitneyu(sample_1, sample_2, use_continuity=True)
    except ValueError:
      # If sum of ranks of values in |sample_1| and |sample_2| is equal,
      # scipy.stats.mannwhitneyu raises ValueError. Treat this as a 1.0 p-value
      # (indistinguishable).
      return (False, 1.0)

    if IsScipyMannTestOneSided():
      p_value = p_value * 2 if p_value < 0.5 else 1

  elif test == KOLMOGOROV:
    _, p_value = stats.ks_2samp(sample_1, sample_2)

  elif test == WELCH:
    if not (IsNormallyDistributed(sample_1, significance_level)[0] and
            IsNormallyDistributed(sample_2, significance_level)[0]):
      raise NonNormalSampleError()
    _, p_value = stats.ttest_ind(sample_1, sample_2, equal_var=False)
  # TODO: Add k sample anderson darling test

  is_different = p_value <= significance_level
  return is_different, p_value


def AssertThatKeysMatch(result_dict_1, result_dict_2):
  """Raises an exception if benchmark dicts do not contain the same metrics."""
  if result_dict_1.viewkeys() != result_dict_2.viewkeys():
    raise DictMismatchError()


def AreBenchmarkResultsDifferent(result_dict_1, result_dict_2, test=MANN,
                                 significance_level=0.05):
  """Runs the given test on the results of each metric in the benchmarks.

  Checks if the dicts have been created from the same benchmark, i.e. if
  metric names match (e.g. first_non_empty_paint_time). Then runs the specified
  statistical test on each metric's samples to find if they vary significantly.

  Args:
    result_dict_1: Benchmark result dict of format {metric: list of values}.
    result_dict_2: Benchmark result dict of format {metric: list of values}.
    test: Statistical test that is used.
    significance_level: The significance level the p-value is compared against.

  Returns:
    test_outcome_dict: Format {metric: (bool is_different, p-value)}.
  """
  AssertThatKeysMatch(result_dict_1, result_dict_2)

  test_outcome_dict = {}
  for metric in result_dict_1:
    is_different, p_value = AreSamplesDifferent(result_dict_1[metric],
                                                result_dict_2[metric],
                                                test, significance_level)
    test_outcome_dict[metric] = (is_different, p_value)

  return test_outcome_dict


def ArePagesetBenchmarkResultsDifferent(result_dict_1, result_dict_2, test=MANN,
                                        significance_level=0.05):
  """Runs the given test on the results of each metric/page combination.

  Checks if the dicts have been created from the same benchmark, i.e. if metric
  names and pagesets match (e.g. metric first_non_empty_paint_time and page
  Google.com). Then runs the specified statistical test on each metric/page
  combination's sample to find if they vary significantly.

  Args:
    result_dict_1: Benchmark result dict
    result_dict_2: Benchmark result dict
    test: Statistical test that is used.
    significance_level: The significance level the p-value is compared against.

  Returns:
    test_outcome_dict: Format {metric: {page: (bool is_different, p-value)}}
  """
  AssertThatKeysMatch(result_dict_1, result_dict_2)

  # Pagesets should also match.
  for metric in result_dict_1.iterkeys():
    AssertThatKeysMatch(result_dict_1[metric], result_dict_2[metric])

  test_outcome_dict = {}
  for metric in result_dict_1.iterkeys():
    test_outcome_dict[metric] = {}
    for page in result_dict_1[metric]:
      is_different, p_value = AreSamplesDifferent(result_dict_1[metric][page],
                                                  result_dict_2[metric][page],
                                                  test, significance_level)
      test_outcome_dict[metric][page] = (is_different, p_value)

  return test_outcome_dict
