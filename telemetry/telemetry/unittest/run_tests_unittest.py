# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators
from telemetry.core import util
from telemetry.unittest import run_tests


class MockPossibleBrowser(object):
  def __init__(self, browser_type, os_name, os_version_name,
               supports_tab_control):
    self.browser_type = browser_type
    self.platform = MockPlatform(os_name, os_version_name)
    self.supports_tab_control = supports_tab_control


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
    self.suite = unittest.TestSuite()
    self.suite.addTests(run_tests.Discover(
        util.GetTelemetryDir(), util.GetTelemetryDir(), 'disabled_cases.py'))

  def _GetEnabledTests(self, browser_type, os_name, os_version_name,
                       supports_tab_control):
    # pylint: disable=W0212
    def MockPredicate(test):
      method = getattr(test, test._testMethodName)
      return decorators.IsEnabled(method, MockPossibleBrowser(
          browser_type, os_name, os_version_name, supports_tab_control))

    enabled_tests = set()
    for i in run_tests.FilterSuite(self.suite, MockPredicate)._tests:
      for j in i:
        for k in j:
          enabled_tests.add(k._testMethodName)
    return enabled_tests

  def testSystemMacMavericks(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testMacOnly',
             'testMavericksOnly',
             'testNoChromeOS',
             'testNoWinLinux',
             'testSystemOnly',
             'testHasTabs']),
        self._GetEnabledTests('system', 'mac', 'mavericks', True))

  def testSystemMacLion(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testMacOnly',
             'testNoChromeOS',
             'testNoMavericks',
             'testNoWinLinux',
             'testSystemOnly',
             'testHasTabs']),
        self._GetEnabledTests('system', 'mac', 'lion', True))

  def testCrosGuestChromeOS(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testChromeOSOnly',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testNoWinLinux',
             'testHasTabs']),
        self._GetEnabledTests('cros-guest', 'chromeos', '', True))

  def testCanaryWindowsWin7(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testNoChromeOS',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testWinOrLinuxOnly',
             'testHasTabs']),
        self._GetEnabledTests('canary', 'win', 'win7', True))

  def testDoesntHaveTabs(self):
    self.assertEquals(
        set(['testAllEnabled',
             'testNoChromeOS',
             'testNoMac',
             'testNoMavericks',
             'testNoSystem',
             'testWinOrLinuxOnly']),
        self._GetEnabledTests('canary', 'win', 'win7', False))
