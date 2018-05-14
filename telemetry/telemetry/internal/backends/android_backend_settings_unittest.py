# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from telemetry.internal.backends import android_browser_backend_settings

from devil.android.sdk import version_codes


ANDROID_BACKEND_SETTINGS = (
    android_browser_backend_settings.ANDROID_BACKEND_SETTINGS)


class AndroidBackendSettingsUnittest(unittest.TestCase):
  def testUniqueBrowserTypes(self):
    browser_types = {}
    for new in ANDROID_BACKEND_SETTINGS:
      old = browser_types.get(new.browser_type)
      self.assertIsNone(
          old,
          'duplicate browser type %s: %s and %s' % (new.browser_type, old, new))
      browser_types[new.browser_type] = new

  def testChromeApkOnMarshmallow(self):
    device = mock.Mock()
    device.build_version_sdk = version_codes.MARSHMALLOW
    self.assertEqual(
        android_browser_backend_settings.ANDROID_CHROME.GetApkName(device),
        'Chrome.apk')

  def testMonochromeApkOnNougat(self):
    device = mock.Mock()
    device.build_version_sdk = version_codes.NOUGAT
    self.assertEqual(
        android_browser_backend_settings.ANDROID_CHROME.GetApkName(device),
        'Monochrome.apk')

  def testWebViewApkOnAOSP(self):
    device = mock.Mock()
    device.build_version_sdk = version_codes.NOUGAT
    device.build_description = 'some aosp device on N'
    self.assertEqual(
        android_browser_backend_settings.ANDROID_WEBVIEW.GetApkName(device),
        'SystemWebView.apk')

  def testSystemWebViewApkOnMarshmallow(self):
    device = mock.Mock()
    device.build_version_sdk = version_codes.MARSHMALLOW
    device.build_description = 'some device on M'
    self.assertEqual(
        android_browser_backend_settings.ANDROID_WEBVIEW.GetApkName(device),
        'SystemWebViewGoogle.apk')

  def testMonochromeApkForWebViewOnNougat(self):
    device = mock.Mock()
    device.build_version_sdk = version_codes.NOUGAT
    device.build_description = 'some device on N'
    self.assertEqual(
        android_browser_backend_settings.ANDROID_WEBVIEW.GetApkName(device),
        'Monochrome.apk')
