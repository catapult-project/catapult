# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for the Skia Perf export pipeline."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math


def FloatHack(f):
  """Workaround JSON inserts not supporting inf and NaN values.

  Somewhere between Beam and the BigQuery streaming inserts API infinities and
  NaNs break if passed as is, apparently because JSON cannot represent these
  values natively.  Fortunately BigQuery appears happy to cast string values
  into floats, so we just have to intercept these values and substitute strings.

  Nones, and floats other than inf and NaN, are returned unchanged.

  Args:
    f: The float value to check.

  Returns:
    The original value, or a string representation for Inf/NaN.
  """
  if f is None:
    return None
  if math.isinf(f):
    return 'inf' if f > 0 else '-inf'
  if math.isnan(f):
    return 'NaN'
  return f
