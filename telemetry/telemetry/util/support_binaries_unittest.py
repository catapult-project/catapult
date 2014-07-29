# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry import decorators
from telemetry.util import support_binaries

class SupportBinariesTest(unittest.TestCase):
  @decorators.Enabled('linux')
  def testFindPath(self):
    md5sum_path = support_binaries.FindPath('md5sum_bin_host', 'linux')
    self.assertNotEquals(md5sum_path, None)
    self.assertTrue(os.path.isabs(md5sum_path))
