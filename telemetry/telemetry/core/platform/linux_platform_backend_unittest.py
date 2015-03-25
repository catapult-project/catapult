# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core.platform import linux_platform_backend
from telemetry.core import util
from telemetry import decorators

class TestBackend(
    linux_platform_backend.LinuxPlatformBackend):

  def __init__(self):
    super(TestBackend, self).__init__()
    self._mock_files = {}

  def SetMockFile(self, filename, output):
    self._mock_files[filename] = output

  def GetFileContents(self, filename):
    return self._mock_files[filename]

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def GetSystemCommitCharge(self):
    raise NotImplementedError()

  def StopVideoCapture(self):
    raise NotImplementedError()

  def StartVideoCapture(self, min_bitrate_mbps):
    raise NotImplementedError()

  def GetSystemTotalPhysicalMemory(self):
    raise NotImplementedError()


class LinuxPlatformBackendTest(unittest.TestCase):
  @decorators.Enabled('linux')
  def testGetOSVersionNameSaucy(self):
    backend = TestBackend()
    path = os.path.join(util.GetUnittestDataDir(), 'ubuntu-saucy-lsb-release')
    with open(path) as f:
      backend.SetMockFile('/etc/lsb-release', f.read())

    self.assertEqual(backend.GetOSVersionName(), 'saucy')

  @decorators.Enabled('linux')
  def testGetOSVersionNameArch(self):
    backend = TestBackend()
    path = os.path.join(util.GetUnittestDataDir(), 'arch-lsb-release')
    with open(path) as f:
      backend.SetMockFile('/etc/lsb-release', f.read())

    # a distribution may not have a codename or a release number. We just check
    # that GetOSVersionName doesn't raise an exception
    backend.GetOSVersionName()
