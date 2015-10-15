# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.backends.chrome import android_browser_finder
from telemetry.internal.browser import browser_options
from telemetry.testing import system_stub
import mock


class FakeAndroidPlatform(object):
  def __init__(self, can_launch):
    self._platform_backend = None
    self._unittest_can_launch = can_launch

  def CanLaunchApplication(self, _):
    return self._unittest_can_launch


class AndroidBrowserFinderTest(unittest.TestCase):
  def setUp(self):
    self.finder_options = browser_options.BrowserFinderOptions()

    # Mock out what's needed for testing with exact APKs
    self._android_browser_finder_stub = system_stub.Override(
        android_browser_finder, ['os'])
    self._patcher = mock.patch('devil.android.apk_helper.GetPackageName')
    self._get_package_name_mock = self._patcher.start()


  def tearDown(self):
    self._android_browser_finder_stub.Restore()
    self._patcher.stop()

  def testNoPlatformReturnsEmptyList(self):
    fake_platform = None
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertEqual([], possible_browsers)

  def testCanLaunchAlwaysTrueReturnsAllExceptExact(self):
    fake_platform = FakeAndroidPlatform(can_launch=True)
    all_types = set(
        android_browser_finder.FindAllBrowserTypes(self.finder_options))
    expected_types = all_types - set(('exact',))
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertEqual(
        expected_types,
        set([b.browser_type for b in possible_browsers]))

  def testCanLaunchAlwaysTrueWithExactApkReturnsAll(self):
    self._android_browser_finder_stub.os.path.files.append(
        '/foo/ContentShell.apk')
    self.finder_options.browser_executable = '/foo/ContentShell.apk'
    self._get_package_name_mock.return_value = 'org.chromium.content_shell_apk'

    fake_platform = FakeAndroidPlatform(can_launch=True)
    expected_types = set(
        android_browser_finder.FindAllBrowserTypes(self.finder_options))
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertEqual(
        expected_types,
        set([b.browser_type for b in possible_browsers]))

  def testErrorWithUnknownExactApk(self):
    self._android_browser_finder_stub.os.path.files.append(
        '/foo/ContentShell.apk')
    self.finder_options.browser_executable = '/foo/ContentShell.apk'
    self._get_package_name_mock.return_value = 'org.unknown.app'

    fake_platform = FakeAndroidPlatform(can_launch=True)
    self.assertRaises(Exception,
        android_browser_finder._FindAllPossibleBrowsers,
        self.finder_options, fake_platform)

  def testErrorWithNonExistantExactApk(self):
    self.finder_options.browser_executable = '/foo/ContentShell.apk'
    self._get_package_name_mock.return_value = 'org.chromium.content_shell_apk'

    fake_platform = FakeAndroidPlatform(can_launch=True)
    self.assertRaises(Exception,
        android_browser_finder._FindAllPossibleBrowsers,
        self.finder_options, fake_platform)

  def testNoErrorWithUnrecognizedApkName(self):
    self._android_browser_finder_stub.os.path.files.append(
        '/foo/unknown.apk')
    self.finder_options.browser_executable = '/foo/unknown.apk'

    fake_platform = FakeAndroidPlatform(can_launch=True)
    possible_browsers = android_browser_finder._FindAllPossibleBrowsers(
        self.finder_options, fake_platform)
    self.assertNotIn('exact', [b.browser_type for b in possible_browsers])


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
