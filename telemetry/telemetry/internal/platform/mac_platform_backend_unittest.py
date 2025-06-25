# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
import unittest

from telemetry.core import platform as platform_module
from telemetry.core import os_version
from telemetry import decorators


class MacPlatformBackendTest(unittest.TestCase):

  def testVersionComparison(self):
    macos33 = os_version.OSVersion('macos33',
                                   3300)  # from the far spooky future
    macos26 = os_version.OSVersion('macos26', 2600)

    # Comparisons of the class objects.
    self.assertGreater(macos33, macos26)
    self.assertGreater(macos26, os_version.SONOMA)
    self.assertGreater(os_version.SEQUOIA, os_version.SONOMA)
    self.assertGreater(os_version.SONOMA, os_version.VENTURA)
    self.assertGreater(os_version.VENTURA, os_version.MONTEREY)

    # Implicit conversion of the object to its friendly name.
    self.assertEqual(macos26, 'macos26')
    self.assertEqual('%s!' % macos26, 'macos26!')
    self.assertEqual(''.join([macos26, '!']), 'macos26!')
    self.assertEqual(macos26.upper(), 'MACOS26')

  @decorators.Enabled('mac')
  def testGetSystemLogSmoke(self):
    platform = platform_module.GetHostPlatform()
    self.assertTrue(platform.GetSystemLog())
