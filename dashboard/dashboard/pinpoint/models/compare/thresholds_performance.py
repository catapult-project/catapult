# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script for calculating p-value thresholds for performance comparisons."""

import math

from scipy import stats


def main():
  # Pick two representative samples of size 10.
  a = [0] * 10
  b = [0] * 9 + [1]

  print '1.0000'
  for i in xrange(1, 12):
    # Take the samples' p-value. Repeat for increasing i,
    # multiplying the sample size by i each time.
    pvalue = stats.mannwhitneyu(a * i, b * i, alternative='two-sided').pvalue
    # Round up.
    print '%.4f' % (math.ceil(pvalue * 10000) / 10000)


if __name__ == '__main__':
  main()
