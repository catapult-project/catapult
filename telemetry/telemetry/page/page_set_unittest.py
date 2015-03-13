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
    expected_serving_dirs = set([os.path.join(real_directory_path, 'a', 'b')])
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

  def testFormingPageSetFromSubPageSet(self):
    page_set_a = page_set.PageSet()
    pages = [
        page.Page('http://foo.com', page_set_a),
        page.Page('http://bar.com', page_set_a),
        ]
    for p in pages:
      page_set_a.AddUserStory(p)

    # Form page_set_b from sub page_set_a.
    page_set_b = page_set.PageSet()
    for p in pages:
      p.TransferToPageSet(page_set_b)
    page_set_b.AddUserStory(page.Page('http://baz.com', page_set_b))
    self.assertEqual(0, len(page_set_a.pages))
    self.assertEqual(
        set(['http://foo.com', 'http://bar.com', 'http://baz.com']),
        set(p.url for p in page_set_b.pages))
    for p in page_set_b.pages:
      self.assertIs(page_set_b, p.page_set)
