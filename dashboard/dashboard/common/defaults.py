# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Module for default values.

This module contains many of the default values we use in various places in
the codebase.

NOTE: We should minimise the dependencies from this module.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

# Maximum number of points to consider at one time.
MAX_WINDOW_SIZE = 50

# Minimum number of points in a segment. This can help filter out erroneous
# results by ignoring results that were found from looking at too few points.
MIN_SEGMENT_SIZE = 6

# Minimum absolute difference between medians before and after.
MIN_ABSOLUTE_CHANGE = 0

# Minimum relative difference between medians before and after.
MIN_RELATIVE_CHANGE = 0.01

# "Steppiness" is a number between 0 and 1 that indicates how similar the
# shape is to a perfect step function, where 1 represents a step function.
MIN_STEPPINESS = 0.5

# The "standard deviation" is based on a subset of points in the series.
# This parameter is the minimum acceptable ratio of the relative change
# and this standard deviation.
MULTIPLE_OF_STD_DEV = 2.5
