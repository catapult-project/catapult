# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.compare import kolmogorov_smirnov
from dashboard.pinpoint.models.compare import mann_whitney_u


DIFFERENT = 'different'
PENDING = 'pending'
SAME = 'same'
UNKNOWN = 'unknown'


_HIGH_THRESHOLDS = (
    1.0000, 0.3682, 0.1625, 0.0815, 0.0428, 0.0230,
    0.0126, 0.0070, 0.0039, 0.0022, 0.0013, 0.0007,
)

_LOW_THRESHOLD = 0.001


def Compare(values_a, values_b, attempt_count):
  """Decide whether two samples are the same, different, or unknown.

  Arguments:
    values_a: A list of sortable values. They don't need to be numeric.
    values_b: A list of sortable values. They don't need to be numeric.
    attempt_count: The total number of attempts made.

  Returns:
    DIFFERENT: The samples likely come from different distributions.
        Reject the null hypothesis.
    SAME: Not enough evidence to say that the samples come from different
        distributions. Fail to reject the null hypothesis.
    UNKNOWN: Not enough evidence to say that the samples come from different
        distributions, but it looks a little suspicious, and we would like more
        data before making a final decision.
  """
  if not (values_a and values_b):
    # A sample has no values in it.
    return UNKNOWN

  # MWU is bad at detecting changes in variance, and K-S is bad with discrete
  # distributions. So use both. We want low p-values for the below examples.
  #        a                     b               MWU(a, b)  KS(a, b)
  # [0]*20            [0]*15+[1]*5                0.0097     0.4973
  # range(10, 30)     range(10)+range(30, 40)     0.4946     0.0082
  p_value = min(
      kolmogorov_smirnov.KolmogorovSmirnov(values_a, values_b),
      mann_whitney_u.MannWhitneyU(values_a, values_b))

  if p_value < _LOW_THRESHOLD:
    # The p-value is less than the significance level. Reject the null
    # hypothesis.
    return DIFFERENT

  index = min(attempt_count / 20, len(_HIGH_THRESHOLDS) - 1)
  questionable_significance_level = _HIGH_THRESHOLDS[index]
  if p_value <= questionable_significance_level:
    # The p-value is not less than the significance level, but it's small enough
    # to be suspicious. We'd like to investigate more closely.
    return UNKNOWN

  # The p-value is quite large. We're not suspicious that the two samples might
  # come from different distributions, and we don't care to investigate more.
  return SAME
