# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry import benchmark
from telemetry.internal.platform import android_device
from telemetry.internal.platform import cros_device
from telemetry.internal.platform import desktop_device
from telemetry.internal.platform import device_finder
from telemetry.story import expectations

class DeviceFinderTest(unittest.TestCase):
  def testGetDeviceFindersDesktop(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL_DESKTOP])
    finders = device_finder._GetDeviceFinders(platforms)
    self.assertFalse(android_device in finders)
    self.assertTrue(cros_device in finders)
    self.assertTrue(desktop_device in finders)

  def testGetDeviceFindersMobile(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL_ANDROID])
    finders = device_finder._GetDeviceFinders(platforms)
    self.assertTrue(android_device in finders)
    self.assertFalse(cros_device in finders)
    self.assertFalse(desktop_device in finders)

  def testGetDeviceFindersAndroidConditionals(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ANDROID_NEXUS6_WEBVIEW])
    finders = device_finder._GetDeviceFinders(platforms)
    self.assertTrue(android_device in finders)
    self.assertFalse(cros_device in finders)
    self.assertFalse(desktop_device in finders)

  def testGetDeviceFindersMac(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.MAC_10_11])
    finders = device_finder._GetDeviceFinders(platforms)
    self.assertFalse(android_device in finders)
    self.assertFalse(cros_device in finders)
    self.assertTrue(desktop_device in finders)

  def testGetDeviceFindersAll(self):
    platforms = benchmark.Benchmark.GetSupportedPlatforms([
        expectations.ALL])
    finders = device_finder._GetDeviceFinders(platforms)
    self.assertTrue(android_device in finders)
    self.assertTrue(cros_device in finders)
    self.assertTrue(desktop_device in finders)
