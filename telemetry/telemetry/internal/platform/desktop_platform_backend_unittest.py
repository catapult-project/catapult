# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import mock

from telemetry.internal.platform import linux_platform_backend
from telemetry.internal.platform import win_platform_backend
from telemetry.internal.platform import cros_platform_backend
from telemetry.internal.platform import mac_platform_backend

class DesktopPlatformBackendTest(unittest.TestCase):
  def testDesktopTagInTypExpectationsTags(self):
    desktop_backends = [
        linux_platform_backend.LinuxPlatformBackend,
        win_platform_backend.WinPlatformBackend,
        cros_platform_backend.CrosPlatformBackend,
        mac_platform_backend.MacPlatformBackend]
    for db in desktop_backends:
      with mock.patch.object(db, 'GetOSVersionDetailString', return_value=''):
        with mock.patch.object(db, 'GetOSVersionName', return_value=''):
          self.assertIn('desktop', db().GetTypExpectationsTags())
