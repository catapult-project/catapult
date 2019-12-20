# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest
import match_policy
import sheriff_config_pb2
import sheriff_pb2


class MatchPolicyTest(unittest.TestCase):

  def testOverlap(self):
    request = sheriff_config_pb2.MatchRequest()
    configs = [
        ("", "", sheriff_pb2.Subscription(
            name="Private",
            visibility=sheriff_pb2.Subscription.INTERNAL_ONLY,
        )),
        ("", "", sheriff_pb2.Subscription(
            name="Public",
            visibility=sheriff_pb2.Subscription.PUBLIC,
        )),
    ]
    configs = match_policy.FilterSubscriptionsByPolicy(request, configs)
    self.assertEqual(["Private"], [s.name for _, _, s in configs])
