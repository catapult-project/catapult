# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import StringIO
import unittest

from telemetry.internal import snap_page_util
from telemetry.testing import options_for_unittests
from telemetry.internal.browser import browser_finder
from telemetry.internal.util import path


class SnapPageTest(unittest.TestCase):
  def setUp(self):
    self.finder_options = options_for_unittests.GetCopy()
    browser_to_create = browser_finder.FindBrowser(self.finder_options)
    self.platform = browser_to_create.platform
    self.platform.network_controller.InitializeIfNeeded()

  def tearDown(self):
    self.platform.network_controller.Close()

  def testSnappingSimplePage(self):
    self.platform.SetHTTPServerDirectories(path.GetUnittestDataDir())
    html_file_path = os.path.join(path.GetUnittestDataDir(), 'green_rect.html')
    url = self.platform.http_server.UrlOf(html_file_path)
    outfile = StringIO.StringIO()
    snap_page_util.SnapPage(
        self.finder_options, url, interactive=False, snapshot_file=outfile)
    self.assertIn('id="green"', outfile.getvalue())
