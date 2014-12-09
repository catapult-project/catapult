# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import browser_options
from telemetry.core.backends.chrome import android_browser_finder


class FakeAndroidPlatform():
  def __init__(self, can_launch):
    self._platform_backend = None
    self._unittest_can_launch = can_launch

  def CanLaunchApplication(self, _):
    return self._unittest_can_launch


class AndroidBrowserFinderTest(unittest.TestCase):
  def setUp(self):
    self.finder_options = browser_options.BrowserFinderOptions()

  def testNoPlatformReturnsEmptyList(self):
    fake_platform = None
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertEqual([], possible_browsers)

  def testCanLaunchAlwaysTrueReturnsAll(self):
    fake_platform = FakeAndroidPlatform(can_launch=True)
    expected_types = set(
        android_browser_finder.FindAllBrowserTypes(self.finder_options))
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertEqual(
        expected_types,
        set([b.browser_type for b in possible_browsers]))


class FakePossibleBrowser(object):
  def __init__(self, last_modification_time):
    self._last_modification_time = last_modification_time

  def last_modification_time(self):
    return self._last_modification_time


class SelectDefaultBrowserTest(unittest.TestCase):
  def testEmptyListGivesNone(self):
    self.assertIsNone(android_browser_finder.SelectDefaultBrowser([]))

  def testSinglePossibleReturnsSame(self):
    possible_browsers = [FakePossibleBrowser(last_modification_time=1)]
    self.assertIs(
      possible_browsers[0],
      android_browser_finder.SelectDefaultBrowser(possible_browsers))

  def testListGivesNewest(self):
    possible_browsers = [
        FakePossibleBrowser(last_modification_time=2),
        FakePossibleBrowser(last_modification_time=3),  # newest
        FakePossibleBrowser(last_modification_time=1),
        ]
    self.assertIs(
      possible_browsers[1],
      android_browser_finder.SelectDefaultBrowser(possible_browsers))
