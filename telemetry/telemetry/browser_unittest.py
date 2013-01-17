# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry import browser_finder
from telemetry import options_for_unittests

class BrowserTest(unittest.TestCase):
  def testBrowserCreation(self):
    options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(options)
    if not browser_to_create:
      raise Exception('No browser found, cannot continue test.')
    with browser_to_create.Create() as b:
      self.assertEquals(1, len(b.tabs))

      # Different browsers boot up to different things
      assert b.tabs[0].url

  def testCommandLineOverriding(self):
    # This test starts the browser with --enable-benchmarking, which should
    # create a chrome.Interval namespace. This tests whether the command line is
    # being set.
    options = options_for_unittests.GetCopy()

    flag1 = '--user-agent=telemetry'
    options.extra_browser_args.append(flag1)

    browser_to_create = browser_finder.FindBrowser(options)
    with browser_to_create.Create() as b:
      t = b.tabs[0]
      t.Navigate('http://www.google.com/')
      t.WaitForDocumentReadyStateToBeInteractiveOrBetter()
      self.assertEquals(t.EvaluateJavaScript('navigator.userAgent'),
                        'telemetry')

  def testVersionDetection(self):
    options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(options)
    with browser_to_create.Create() as b:
      # pylint: disable=W0212
      self.assertGreater(b._browser_backend._inspector_protocol_version, 0)
      self.assertGreater(b._browser_backend._chrome_branch_number, 0)
      self.assertGreater(b._browser_backend._webkit_base_revision, 0)

  def testNewCloseTab(self):
    options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(options)
    with browser_to_create.Create() as b:
      existing_tab = b.tabs[0]
      self.assertEquals(1, len(b.tabs))
      existing_tab_url = existing_tab.url

      new_tab = b.tabs.New()
      self.assertEquals(2, len(b.tabs))
      self.assertEquals(existing_tab.url, existing_tab_url)
      self.assertEquals(new_tab.url, 'about:blank')

      new_tab.Close()
      self.assertEquals(1, len(b.tabs))
      self.assertEquals(existing_tab.url, existing_tab_url)
