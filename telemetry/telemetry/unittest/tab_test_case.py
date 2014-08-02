# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.core import browser_finder
from telemetry.core import util
from telemetry.unittest import options_for_unittests


class TabTestCase(unittest.TestCase):
  _extra_browser_args = []

  def __init__(self, *args):
    super(TabTestCase, self).__init__(*args)

    self._tab = None
    self.test_file_path = None
    self.test_url = None

  @classmethod
  def setUpClass(cls):
    options = options_for_unittests.GetCopy()
    cls.CustomizeBrowserOptions(options.browser_options)
    if cls._extra_browser_args:
      options.AppendExtraBrowserArgs(cls._extra_browser_args)

    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      raise Exception('No browser found, cannot continue test.')

    cls._browser = None
    try:
      cls._browser = browser_to_create.Create()
      cls._browser.Start()
    except:
      cls.tearDownClass()
      raise

  def setUp(self):
    if self._browser.supports_tab_control:
      self._tab = self._browser.tabs.New()
      while len(self._browser.tabs) > 1:
        self._browser.tabs[0].Close()
    else:
      if not self._browser.tabs:
        self.tearDownClass()
        self.setUpClass()
      self._tab = self._browser.tabs[0]
    self._tab.Navigate('about:blank')
    self._tab.WaitForDocumentReadyStateToBeInteractiveOrBetter()

  @classmethod
  def tearDownClass(cls):
    if cls._browser:
      cls._browser.Close()

  @classmethod
  def CustomizeBrowserOptions(cls, options):
    """Override to add test-specific options to the BrowserOptions object"""
    pass

  def Navigate(self, filename, script_to_evaluate_on_commit=None):
    """Navigates |tab| to |filename| in the unittest data directory.

    Also sets up http server to point to the unittest data directory.
    """
    self._browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
    self.test_file_path = os.path.join(util.GetUnittestDataDir(), filename)
    self.test_url = self._browser.http_server.UrlOf(self.test_file_path)
    self._tab.Navigate(self.test_url, script_to_evaluate_on_commit)
    self._tab.WaitForDocumentReadyStateToBeComplete()
