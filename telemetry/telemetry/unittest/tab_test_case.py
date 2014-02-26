# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.core import util
from telemetry.unittest import options_for_unittests


class TabTestCase(unittest.TestCase):
  def __init__(self, *args):
    self._extra_browser_args = []
    self.test_file_path = None
    super(TabTestCase, self).__init__(*args)

  def setUp(self):
    self._browser = None
    self._tab = None
    options = options_for_unittests.GetCopy()

    self.CustomizeBrowserOptions(options)

    if self._extra_browser_args:
      options.AppendExtraBrowserArgs(self._extra_browser_args)

    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      raise Exception('No browser found, cannot continue test.')
    try:
      self._browser = browser_to_create.Create()
      self._browser.Start()
      self._tab = self._browser.tabs[0]
      self._tab.Navigate('about:blank')
      self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

    except:
      self.tearDown()
      raise

  def tearDown(self):
    if self._browser:
      self._browser.Close()

  def CustomizeBrowserOptions(self, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  def Navigate(self, filename, script_to_evaluate_on_commit=None):
    """Navigates |tab| to |filename| in the unittest data directory.

    Also sets up http server to point to the unittest data directory.
    """
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self.test_file_path = os.path.join(util.GetUnittestDataDir(), filename)
    self._tab.Navigate(self._browser.http_server.UrlOf(self.test_file_path),
                       script_to_evaluate_on_commit)
    self._tab.WaitForDocumentReadyStateToBeComplete()
