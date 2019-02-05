# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

class PassingTest(unittest.TestCase):
  def test_pass(self):
    pass

class SkipTest(unittest.TestCase):
  def test_skip(self):
    self.skipTest('SKIPPING TEST')
