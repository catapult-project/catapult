# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.unittest import test


# These are not real unittests.
# They are merely to test our Enable/Disable annotations.
class DisabledCases(unittest.TestCase):

  def testAllEnabled(self):
    pass

  @test.Disabled
  def testAllDisabled(self):
    pass

  @test.Enabled('mavericks')
  def testMavericksOnly(self):
    pass

  @test.Disabled('mavericks')
  def testNoMavericks(self):
    pass

  @test.Enabled('mac')
  def testMacOnly(self):
    pass

  @test.Disabled('mac')
  def testNoMac(self):
    pass

  @test.Enabled('chromeos')
  def testChromeOSOnly(self):
    pass

  @test.Disabled('chromeos')
  def testNoChromeOS(self):
    pass

  @test.Enabled('win', 'linux')
  def testWinOrLinuxOnly(self):
    pass

  @test.Disabled('win', 'linux')
  def testNoWinLinux(self):
    pass

  @test.Enabled('system')
  def testSystemOnly(self):
    pass

  @test.Disabled('system')
  def testNoSystem(self):
    pass

  @test.Enabled('has tabs')
  def testHasTabs(self):
    pass
