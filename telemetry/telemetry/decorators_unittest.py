# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry import decorators


class FakePlatform(object):
  def GetOSName(self):
    return 'os_name'

  def GetOSVersionName(self):
    return 'os_version_name'


class FakePossibleBrowser(object):
  def __init__(self):
    self.browser_type = 'browser_type'
    self.platform = FakePlatform()
    self.supports_tab_control = False


class FakeTest(object):
  def SetEnabledStrings(self, enabled_strings):
    # pylint: disable=W0201
    self._enabled_strings = enabled_strings

  def SetDisabledStrings(self, disabled_strings):
    # pylint: disable=W0201
    self._disabled_strings = disabled_strings


class TestShouldSkip(unittest.TestCase):
  def testEnabledStrings(self):
    test = FakeTest()
    possible_browser = FakePossibleBrowser()

    # When no enabled_strings is given, everything should be enabled.
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_version_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['os_name', 'another_os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name', 'os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetEnabledStrings(['another_os_name', 'another_os_version_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

  def testDisabledStrings(self):
    test = FakeTest()
    possible_browser = FakePossibleBrowser()

    # When no disabled_strings is given, nothing should be disabled.
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_version_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['os_name', 'another_os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name', 'os_name'])
    self.assertTrue(decorators.ShouldSkip(test, possible_browser)[0])

    test.SetDisabledStrings(['another_os_name', 'another_os_version_name'])
    self.assertFalse(decorators.ShouldSkip(test, possible_browser)[0])
