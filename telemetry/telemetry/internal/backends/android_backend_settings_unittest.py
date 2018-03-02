# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.backends import android_browser_backend_settings


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

  def testUniquePackageNames(self):
    package_names = {}
    for new in ANDROID_BACKEND_SETTINGS:
      old = package_names.get(new.package)
      self.assertIsNone(
          old,
          'duplicate package name %s: %s and %s' % (new.package, old, new))
      package_names[new.package] = new
