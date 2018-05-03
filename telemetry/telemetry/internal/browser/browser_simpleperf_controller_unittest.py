# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from devil.android.sdk import version_codes

from telemetry.internal.browser import browser_simpleperf_controller


class FakeDevice(object):
  def __init__(self, build_version_sdk):
    super(FakeDevice, self).__init__()
    self.build_version_sdk = build_version_sdk


class FakeAndroidPlatformBackend(object):
  def __init__(self, build_version_sdk):
    super(FakeAndroidPlatformBackend, self).__init__()
    self.device = FakeDevice(build_version_sdk)

  def GetOSName(self):
    return 'android'


class FakeLinuxPlatformBackend(object):
  def GetOSName(self):
    return 'linux'


class FakeBrowser(object):
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend


class BrowserSimpleperfControllerTest(unittest.TestCase):
  def _RunTest(self, browser, periods, expected_call_count):
    controller = browser_simpleperf_controller.BrowserSimpleperfController(
        '', periods, 1)
    controller.DidStartBrowser(browser)
    with mock.patch.object(
        controller,
        '_StartSimpleperf',
        new=mock.Mock(return_value=None)) as start_simpleperf_mock:
      with controller.SamplePeriod('test'):
        pass
      self.assertEqual(start_simpleperf_mock.call_count, expected_call_count)

  def testSupportedAndroid(self):
    browser = FakeBrowser(FakeAndroidPlatformBackend(version_codes.OREO))
    self._RunTest(browser, [], expected_call_count=0)
    self._RunTest(browser, ['test'], expected_call_count=1)

  def testUnsupportedAndroid(self):
    browser = FakeBrowser(FakeAndroidPlatformBackend(version_codes.KITKAT))
    self._RunTest(browser, [], expected_call_count=0)
    self._RunTest(browser, ['test'], expected_call_count=0)

  def testDesktop(self):
    browser = FakeBrowser(FakeLinuxPlatformBackend())
    self._RunTest(browser, [], expected_call_count=0)
    self._RunTest(browser, ['test'], expected_call_count=0)
