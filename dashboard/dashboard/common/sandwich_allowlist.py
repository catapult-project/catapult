# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

from dashboard.common import feature_flags

BLOCKED_SUBSCRIPTIONS = []

BLOCKED_BENCHMARKS = []

BLOCKED_DEVICES = []


def CheckAllowlist(subscription, benchmark, cfg):
  '''Check that the subscription, benchmark, and device are
    CABE compatible.

    Args:
      subscription: regression subscription
      benchmark: regression benchmark
      cfg: regression configuration

    Returns:
        True if allowed, False if not.
    '''
  if (feature_flags.SANDWICH_VERIFICATION
      and subscription not in BLOCKED_SUBSCRIPTIONS
      and benchmark not in BLOCKED_BENCHMARKS and cfg not in BLOCKED_DEVICES):
    return True

  return False
