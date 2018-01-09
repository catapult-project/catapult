# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.backends.chrome import chrome_browser_backend_unittest
from telemetry.internal.backends.chrome import chrome_startup_args


class StartupArgsTest(unittest.TestCase):
  """Test expected inputs for GetBrowserStartupArgs."""

  def testFeaturesMerged(self):
    browser_options = chrome_browser_backend_unittest.FakeBrowserOptions()
    browser_options.AppendExtraBrowserArgs([
        '--disable-features=Feature1,Feature2',
        '--disable-features=Feature2,Feature3',
        '--enable-features=Feature4,Feature5',
        '--enable-features=Feature5,Feature6',
        '--foo'])

    startup_args = chrome_startup_args.GetFromBrowserOptions(browser_options)
    self.assertTrue('--foo' in startup_args)
    # Make sure there's only once instance of --enable/disable-features and it
    # contains all values
    disable_count = 0
    enable_count = 0
    # Merging is done using using sets, so any order is correct
    for arg in startup_args:
      if arg.startswith('--disable-features='):
        split_arg = arg.split('=', 1)[1].split(',')
        self.assertEquals({'Feature1', 'Feature2', 'Feature3'}, set(split_arg))
        disable_count += 1
      elif arg.startswith('--enable-features='):
        split_arg = arg.split('=', 1)[1].split(',')
        self.assertEquals({'Feature4', 'Feature5', 'Feature6'}, set(split_arg))
        enable_count += 1
    self.assertEqual(1, disable_count)
    self.assertEqual(1, enable_count)
