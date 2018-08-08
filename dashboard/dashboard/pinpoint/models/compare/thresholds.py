# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Thresholds used for hypothesis testing.

The "low threshold" is the traditional significance threshold. If the p-value is
below the "low threshold", we say the two samples come from different
distributions (reject the null hypothesis).

We also define a "high threshold". If the p-value is above the "high threshold",
we say the two samples come from the same distribution (reject the alternative
hypothesis).

If the p-value is in between the two thresholds, we fail to reject either
hypothesis. This means we need more information to make a decision. As the
sample sizes increase, the high threshold decreases until it crosses the
low threshold. This way, there's a limit on the number of repeats.
"""


def HighThreshold(mode, magnitude, sample_size):
  """Returns the high threshold for hypothesis testing.

  Args:
    mode: 'functional' or 'performance'. We use different significance
        thresholds for each type.
    magnitude: An estimate of the size of differences to look for. We need
        more values to find smaller differences. If mode is 'functional',
        this is the failure rate, a float between 0 and 1. If mode is
        'performance', this is a multiple of the interquartile range (IQR).
    sample_size: The number of values in each sample.

  Returns:
    The high significance threshold.
  """
  if mode == 'functional':
    thresholds = _HIGH_THRESHOLDS_FUNCTIONAL
    magnitude_index = int(magnitude * 10) - 1
  elif mode == 'performance':
    thresholds = _HIGH_THRESHOLDS_PERFORMANCE
    magnitude_index = int(magnitude * 10) - 10
  else:
    raise NotImplementedError()

  magnitude_index = max(magnitude_index, 0)
  magnitude_index = min(magnitude_index, len(thresholds) - 1)
  sample_size_index = min(sample_size, len(thresholds[magnitude_index])) - 1
  return thresholds[magnitude_index][sample_size_index]


def LowThreshold():
  """Returns the low threshold for hypothesis testing."""
  return 0.01


# Run thresholds_functional.py to generate these numbers.
# The magnitudes are expressed in difference in failure rate.
# The sample sizes start at 1.
_HIGH_THRESHOLDS_FUNCTIONAL = (
    # Magnitude 0.1
    (1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, 1.000, .3285, .3282, .3280, .3278, .3275, .3273, .3271,
     .3269, .3268, .3266, .3264, .3262, .3261, .3259, .3258, .3256, .3255,
     .3254, .3252, .3251, .1590, .1589, .1589, .1589, .1589, .1589, .1588,
     .1588, .1588, .1588, .1587, .1587, .1587, .1587, .1587, .1587, .1586,
     .0827, .0827, .0827, .0827, .0827, .0827, .0827, .0827, .0827, .0827,
     .0827, .0827, .0827, .0828, .0828, .0828, .0444, .0444, .0444, .0445,
     .0445, .0445, .0445, .0445, .0445, .0445, .0445, .0445, .0445, .0446,
     .0446, .0446, .0244, .0244, .0244, .0244, .0244, .0244, .0244, .0244,
     .0244, .0244, .0244, .0245, .0245, .0245, .0135, .0135, .0135, .0135,
     .0136, .0136, .0136, .0136, .0136, .0136, .0136, .0136, .0136, .0136,
     .0136, .0076),
    # Magnitude 0.2
    (1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     .3410, .3399, .3389, .3379, .3371, .3363, .3356, .3350, .3343, .3338,
     .1607, .1606, .1605, .1604, .1603, .1602, .1601, .1601, .0819, .0819,
     .0820, .0820, .0820, .0821, .0821, .0821, .0432, .0433, .0433, .0433,
     .0434, .0434, .0435, .0435, .0233, .0233, .0233, .0234, .0234, .0234,
     .0235, .0127, .0127, .0127, .0128, .0128, .0128, .0128, .0070),
    # Magnitude 0.3
    (1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000,
     1.000, 1.000, .3560, .3532, .3507, .3486, .3467, .3450, .3435, .1625,
     .1623, .1620, .1618, .1616, .0810, .0811, .0812, .0813, .0814, .0418,
     .0419, .0421, .0422, .0423, .0220, .0221, .0222, .0223, .0224, .0118,
     .0118, .0119, .0120, .0063),
    # Magnitude 0.4
    (1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, 1.000, .3682,
     .3634, .3594, .3560, .1647, .1642, .1638, .1634, .0800, .0802, .0804,
     .0806, .0404, .0406, .0409, .0207, .0209, .0210, .0212, .0108, .0109,
     .0110, .0057),
    # Magnitude 0.5
    (1.000, 1.000, 1.000, 1.000, 1.000, 1.000, .3914, .3816, .3741, .3682,
     .1666, .1659, .1652, .0789, .0793, .0796, .0388, .0392, .0192, .0195,
     .0198, .0098),
    # Magnitude 0.6
    (1.000, 1.000, 1.000, 1.000, 1.000, .4047, .3914, .1700, .1686, .1675,
     .0775, .0781, .0366, .0373, .0175, .0180, .0185, .0088),
    # Magnitude 0.7
    (1.000, 1.000, 1.000, .4533, .4238, .4047, .1717, .1700, .0758, .0768,
     .0348, .0156, .0163, .0074),
    # Magnitude 0.8
    (1.000, 1.000, .5050, .4533, .1771, .1740, .0730, .0746, .0322, .0137,
     .0147, .0064),
    # Magnitude 0.9
    (1.000, .6171, .5050, .1814, .0668, .0706, .0279, .0110, .0043),
    # Magnitude 1.0
    (1.000, .1940, .0469, .0132, .0040),
)


# Run thresholds_performance.py to generate these numbers.
# The magnitudes are expressed in multiples of the interquartile range (IQR).
# The sample sizes start at 1.
_HIGH_THRESHOLDS_PERFORMANCE = (
    # Magnitude 1.0
    (1.000, .6986, 1.000, .8853, 1.000, .9362, .8984, .7930, .6589, .5708,
     .4701, .4026, .3299, .2803, .2291, .1936, .1480, .1250, .1021, .0811,
     .0663, .0529, .0433, .0346, .0284, .0228, .0178, .0143, .0118, .0091),
    # Magnitude 1.1
    (1.000, .6986, 1.000, .8853, 1.000, .8102, .7983, .6365, .5365, .4274,
     .3247, .2603, .1999, .1611, .1249, .1012, .0790, .0598, .0472, .0361,
     .0287, .0208, .0167, .0130, .0099),
    # Magnitude 1.2
    (1.000, .6986, 1.000, .8853, .8346, .8102, .6093, .4949, .3773, .2731,
     .2122, .1573, .1240, .0936, .0680, .0523, .0388, .0303, .0211, .0167,
     .0119, .0089),
    # Magnitude 1.3
    (1.000, .6986, 1.000, .8853, .8346, .5752, .4433, .3721, .2510, .1859,
     .1310, .0999, .0649, .0509, .0344, .0250, .0175, .0131, .0094),
    # Magnitude 1.4
    (1.000, .6986, 1.000, .8853, .6761, .4712, .3711, .2272, .1577, .1213,
     .0763, .0531, .0355, .0259, .0162, .0123, .0080),
    # Magnitude 1.5
    (1.000, .6986, 1.000, .8853, .5309, .3785, .2502, .1563, .1120, .0757,
     .0489, .0304, .0211, .0140, .0090),
    # Magnitude 1.6
    (1.000, .6986, 1.000, .6651, .4034, .2980, .2014, .1036, .0774, .0452,
     .0303, .0166, .0120, .0072),
    # Magnitude 1.7
    (1.000, .6986, 1.000, .6651, .4034, .2298, .1252, .0832, .0423, .0258,
     .0181, .0102, .0057),
    # Magnitude 1.8
    (1.000, .6986, .6626, .4705, .2963, .1735, .0967, .0521, .0341, .0173,
     .0105, .0062),
    # Magnitude 1.9
    (1.000, .6986, .6626, .3124, .2101, .1283, .0737, .0406, .0217, .0114,
     .0059),
    # Magnitude 2.0
    (1.000, .6986, .6626, .3124, .1437, .0927, .0553, .0240, .0135, .0073),
    # Magnitude 2.1
    (1.000, .6986, .6626, .3124, .1437, .0656, .0410, .0182, .0105, .0046),
    # Magnitude 2.2
    (1.000, .6986, .3828, .1940, .0947, .0656, .0299, .0136, .0062),
    # Magnitude 2.3
    (1.000, .6986, .3828, .1940, .0947, .0454, .0215, .0101, .0048),
    # Magnitude 2.4
    (1.000, .6986, .3828, .1940, .0601, .0307, .0152, .0075),
    # Magnitude 2.5
    (1.000, .6986, .3828, .1124, .0601, .0307, .0152, .0054),
    # Magnitude 2.6
    (1.000, .6986, .3828, .1124, .0601, .0203, .0106, .0054),
    # Magnitude 2.7
    (1.000, .6986, .1905, .1124, .0368, .0203, .0073),
    # Magnitude 2.8
    (1.000, .6986, .1905, .1124, .0368, .0203, .0073),
    # Magnitude 2.9
    (1.000, .6986, .1905, .0606, .0368, .0131, .0073),
    # Magnitude 3.0
    (1.000, .2453, .1905, .0606, .0216, .0131, .0050),
    # Magnitude 3.1
    (1.000, .2453, .1905, .0606, .0216, .0131, .0050),
    # Magnitude 3.2
    (1.000, .2453, .0809, .0606, .0216, .0083),
    # Magnitude 3.3
    (1.000, .2453, .0809, .0606, .0216, .0083),
    # Magnitude 3.4
    (1.000, .2453, .0809, .0304, .0216, .0083),
    # Magnitude 3.5
    (1.000, .2453, .0809, .0304, .0122, .0083),
    # Magnitude 3.6+
    (1.000, .2453, .0809, .0304, .0122, .0051),
)
