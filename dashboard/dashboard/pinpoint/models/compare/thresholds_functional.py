# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import math

from scipy import stats


# The approximate false negative rate.
P_VALUE = 0.01

# The size of regressions we are trying to detect with the above false
# negative rate. Larger regressions will have a smaller false negative rate.
FAILURE_RATE = 0.1


def main():
  # Print the threshold for every 10 repeats, stopping
  # when the threshold is lower than P_VALUE.
  threshold = 1.0
  for repeat_count in xrange(10, 1000, 10):
    print '%.4f' % (math.ceil(threshold * 10000) / 10000)
    if threshold < P_VALUE:
      break
    threshold = Threshold(P_VALUE, FAILURE_RATE, repeat_count)


def Threshold(p_value, failure_rate, repeat_count):
  # Use the binomial distribution to find the sample of pass/fails where the
  # given sample or more extreme samples have P_VALUE probability of occurring.
  failure_count = int(stats.binom(repeat_count, failure_rate).ppf(p_value))
  a = [0] * repeat_count
  b = [0] * (repeat_count - failure_count) + [1] * failure_count
  try:
    return stats.mannwhitneyu(a, b, alternative='two-sided').pvalue
  except ValueError:
    return 1.0


if __name__ == '__main__':
  main()
