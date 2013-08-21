# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import browser_finder
from telemetry.core import util
from telemetry.unittest import options_for_unittests

class TemporaryHTTPServerTest(unittest.TestCase):
  def testBasicHosting(self):
    options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(options)
    with browser_to_create.Create() as b:
      b.Start()
      b.SetHTTPServerDirectories(util.GetUnittestDataDir())
      t = b.tabs[0]
      t.Navigate(b.http_server.UrlOf('/blank.html'))
      t.WaitForDocumentReadyStateToBeComplete()
      x = t.EvaluateJavaScript('document.body.innerHTML')
      x = x.strip()

      self.assertEquals(x, 'Hello world')
