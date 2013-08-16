# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry.core import discover
from telemetry.core import util

class DiscoverTest(unittest.TestCase):
  def testDiscoverClasses(self):
    base_dir = util.GetUnittestDataDir()
    start_dir = os.path.join(base_dir, 'discoverable_classes')
    base_class = Exception
    classes = discover.DiscoverClasses(start_dir, base_dir, base_class)
    self.assertTrue(len(classes) > 0)

    found_dummy_exception = False
    for c in classes.values():
      if c.__name__ == 'DummyException':
        found_dummy_exception = True
      self.assertTrue(issubclass(c, Exception))

    self.assertTrue(found_dummy_exception)
