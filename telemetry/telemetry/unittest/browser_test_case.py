# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.unittest import options_for_unittests
from telemetry.util import path


class BrowserTestCase(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    options = options_for_unittests.GetCopy()
    cls.CustomizeBrowserOptions(options.browser_options)
    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      raise Exception('No browser found, cannot continue test.')

    cls._browser = None
    try:
      cls._browser = browser_to_create.Create()
    except:
      cls.tearDownClass()
      raise

  @classmethod
  def tearDownClass(cls):
    if cls._browser:
      cls._browser.Close()
      cls._browser = None

  @classmethod
  def CustomizeBrowserOptions(cls, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  @classmethod
  def UrlOfUnittestFile(cls, filename):
    cls._browser.SetHTTPServerDirectories(path.GetUnittestDataDir())
    file_path = os.path.join(path.GetUnittestDataDir(), filename)
    return cls._browser.http_server.UrlOf(file_path)
