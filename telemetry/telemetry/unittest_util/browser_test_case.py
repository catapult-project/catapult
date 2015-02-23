# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.unittest_util import options_for_unittests
from telemetry.util import path

current_browser_options = None
current_browser = None


def teardown_browser():
  global current_browser
  global current_browser_options

  if current_browser:
    current_browser.Close()
  current_browser = None
  current_browser_options = None


class BrowserTestCase(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    global current_browser
    global current_browser_options

    options = options_for_unittests.GetCopy()

    cls.CustomizeBrowserOptions(options.browser_options)
    if not current_browser or (current_browser_options !=
                               options.browser_options):
      if current_browser:
        teardown_browser()

      browser_to_create = browser_finder.FindBrowser(options)
      if not browser_to_create:
        raise Exception('No browser found, cannot continue test.')

      try:
        current_browser = browser_to_create.Create(options)
        current_browser_options = options.browser_options
      except:
        cls.tearDownClass()
        raise
    cls._browser = current_browser
    cls._device = options.device

  @classmethod
  def tearDownClass(cls):
    pass

  @classmethod
  def CustomizeBrowserOptions(cls, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  @classmethod
  def UrlOfUnittestFile(cls, filename):
    cls._browser.SetHTTPServerDirectories(path.GetUnittestDataDir())
    file_path = os.path.join(path.GetUnittestDataDir(), filename)
    return cls._browser.http_server.UrlOf(file_path)
