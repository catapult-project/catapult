# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest

from telemetry.page import page
from telemetry.page import page_set
from telemetry.util import cloud_storage


class TestPageSet(unittest.TestCase):

  def testServingDirs(self):
    directory_path = tempfile.mkdtemp()
    try:
      ps = page_set.PageSet(serving_dirs=['a/b'], file_path=directory_path)
      ps.AddUserStory(page.Page('file://c/test.html', ps, ps.base_dir))
      ps.AddUserStory(page.Page('file://c/test.js', ps, ps.base_dir))
      ps.AddUserStory(page.Page('file://d/e/../test.html', ps, ps.base_dir))
    finally:
      os.rmdir(directory_path)

    real_directory_path = os.path.realpath(directory_path)
    expected_serving_dirs = set([os.path.join(real_directory_path, 'a', 'b'),
                                 os.path.join(real_directory_path, 'c'),
                                 os.path.join(real_directory_path, 'd')])
    self.assertEquals(ps.serving_dirs, expected_serving_dirs)
    self.assertEquals(ps[0].serving_dir, os.path.join(real_directory_path, 'c'))
    self.assertEquals(ps[2].serving_dir, os.path.join(real_directory_path, 'd'))

  def testAbsoluteServingDir(self):
    directory_path = tempfile.mkdtemp()
    try:
      absolute_dir = os.path.join(directory_path, 'a', 'b')
      ps = page_set.PageSet(file_path=directory_path,
                            serving_dirs=['', directory_path, absolute_dir])
      real_directory_path = os.path.realpath(directory_path)
      real_absolute_dir = os.path.realpath(absolute_dir)
      self.assertEquals(ps.serving_dirs, set([real_directory_path,
                                              real_absolute_dir]))
    finally:
      os.rmdir(directory_path)
