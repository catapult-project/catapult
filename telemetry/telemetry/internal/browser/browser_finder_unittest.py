# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry import benchmark
from telemetry.internal.backends.chrome import android_browser_finder
from telemetry.internal.backends.chrome import cros_browser_finder
from telemetry.internal.backends.chrome import desktop_browser_finder
from telemetry.internal.browser import browser_finder
from telemetry.story import expectations


class BrowserFinderTest(unittest.TestCase):
  def testGetBrowserFindersDesktop(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL_DESKTOP])
    finders = browser_finder._GetBrowserFinders(platforms)
    self.assertFalse(android_browser_finder in finders)
    self.assertTrue(cros_browser_finder in finders)
    self.assertTrue(desktop_browser_finder in finders)

  def testGetBrowserFindersMobile(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL_ANDROID])
    finders = browser_finder._GetBrowserFinders(platforms)
    self.assertTrue(android_browser_finder in finders)
    self.assertFalse(cros_browser_finder in finders)
    self.assertFalse(desktop_browser_finder in finders)

  def testGetBrowserFindersAndroidConditionals(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ANDROID_NEXUS6_WEBVIEW])
    finders = browser_finder._GetBrowserFinders(platforms)
    self.assertTrue(android_browser_finder in finders)
    self.assertFalse(cros_browser_finder in finders)
    self.assertFalse(desktop_browser_finder in finders)

  def testGetBrowserFindersMac(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.MAC_10_11])
    finders = browser_finder._GetBrowserFinders(platforms)
    self.assertFalse(android_browser_finder in finders)
    self.assertFalse(cros_browser_finder in finders)
    self.assertTrue(desktop_browser_finder in finders)

  def testGetBrowserFindersAll(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL])
    finders = browser_finder._GetBrowserFinders(platforms)
    self.assertTrue(android_browser_finder in finders)
    self.assertTrue(cros_browser_finder in finders)
    self.assertTrue(desktop_browser_finder in finders)
