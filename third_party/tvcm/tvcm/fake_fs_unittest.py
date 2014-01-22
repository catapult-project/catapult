# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import os

from tvcm import fake_fs

class FakeFSUnittest(unittest.TestCase):
  def testBasic(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/blah/x', 'foobar')
    with fs:
      assert os.path.exists('/blah/x')
      self.assertEquals(
          'foobar',
          open('/blah/x', 'r').read())
