# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Policies to ensure internal or restricted information won't be leaked."""

# Support python3
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging
import sheriff_pb2


def FilterSubscriptionsByPolicy(request, configs):
  def IsPrivate(config):
    _, _, subscription = config
    return subscription.visibility == sheriff_pb2.Subscription.INTERNAL_ONLY
  privates = [IsPrivate(c) for c in configs]
  if any(privates) and not all(privates):
    logging.warn("Private sheriff overlaps with public: %s, %s",
                 request.path, [(config_set, subscription.name)
                                for config_set, _, subscription in configs])
    return [c for c in configs if IsPrivate(c)]
  return configs
