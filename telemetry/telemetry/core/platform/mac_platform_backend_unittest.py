# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform import mac_platform_backend


class MacPlatformBackendTest(unittest.TestCase):
  def testVersionCamparison(self):
    self.assertGreater(mac_platform_backend.MAVERICKS,
                       mac_platform_backend.SNOWLEOPARD)
    self.assertGreater(mac_platform_backend.LION,
                       mac_platform_backend.LEOPARD)
    self.assertEqual(mac_platform_backend.MAVERICKS, 'mavericks')
    self.assertEqual('%s2' % mac_platform_backend.MAVERICKS, 'mavericks2')
    self.assertEqual(''.join([mac_platform_backend.MAVERICKS, '2']),
                     'mavericks2')
    self.assertEqual(mac_platform_backend.LION.upper(), 'LION')
