# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators
from telemetry.core import util
from telemetry.unittest import run_tests


class MockPlatform(object):
  def __init__(self, os_name, os_version_name):
    self.os_name = os_name
    self.os_version_name = os_version_name

  def GetOSName(self):
    return self.os_name

  def GetOSVersionName(self):
    return self.os_version_name


class RunTestsUnitTest(unittest.TestCase):

  def setUp(self):
    self.suite = run_tests.Discover(
        util.GetTelemetryDir(), util.GetTelemetryDir(), 'disabled_cases.py')

  def _GetEnabledTests(self, browser_type, platform):
    # pylint: disable=W0212
    def MockPredicate(test):
      method = getattr(test, test._testMethodName)
      return decorators.IsEnabled(method, browser_type, platform)

    enabled_tests = set()
    for i in run_tests.FilterSuite(self.suite, MockPredicate)._tests:
      for j in i._tests:
        for k in j._tests:
          enabled_tests.add(k._testMethodName)
    return enabled_tests

  def testSystemMacMavericks(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testMacOnly',
             'testMavericksOnly',
             'testNoChromeOS',
             'testNoWinLinux',
             'testSystemOnly']),
        self._GetEnabledTests('system', MockPlatform('mac', 'mavericks')))

  def testSystemMacLion(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testMacOnly',
             'testNoChromeOS',
             'testNoMavericks',
             'testNoWinLinux',
             'testSystemOnly']),
        self._GetEnabledTests('system', MockPlatform('mac', 'lion')))

  def testCrosGuestChromeOS(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testChromeOSOnly',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testNoWinLinux']),
        self._GetEnabledTests('cros-guest', MockPlatform('chromeos', '')))

  def testCanaryWindowsWin7(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testNoChromeOS',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testWinOrLinuxOnly']),
        self._GetEnabledTests('canary', MockPlatform('win', 'win7')))
