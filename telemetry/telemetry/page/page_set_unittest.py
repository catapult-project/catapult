# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import tempfile
import unittest

from telemetry.core import util
from telemetry.page import page
from telemetry.page import page_set
from telemetry.util import cloud_storage

class TestPageSet(unittest.TestCase):

  def testServingDirs(self):
    directory_path = tempfile.mkdtemp()
    try:
      ps = page_set.PageSet(serving_dirs=['a/b'], file_path=directory_path)
      ps.AddPageWithDefaultRunNavigate('file://c/test.html')
      ps.AddPageWithDefaultRunNavigate('file://c/test.js')
      ps.AddPageWithDefaultRunNavigate('file://d/e/../test.html')
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

  def testSuccesfulPythonPageSetLoading(self):
    test_pps_dir = os.path.join(util.GetUnittestDataDir(), 'test_page_set.py')
    pps = page_set.PageSet.FromFile(test_pps_dir)
    self.assertEqual('TestPageSet', pps.__class__.__name__)
    self.assertEqual('A pageset for testing purpose', pps.Description())
    self.assertEqual('data/test.json', pps.archive_data_file)
    self.assertEqual('data/credential', pps.credentials_path)
    self.assertEqual('desktop', pps.user_agent_type)
    self.assertEqual(test_pps_dir, pps.file_path)
    self.assertEqual(page_set.PUBLIC_BUCKET, pps.bucket)
    self.assertEqual(3, len(pps.pages))
    google_page = pps.pages[0]
    self.assertEqual('https://www.google.com', google_page.url)
    self.assertIs(pps, google_page.page_set)
    self.assertTrue(5, google_page.RunGetActionRunner(action_runner=5))

  def testMultiplePythonPageSetsLoading(self):
    test_pps_1_dir = os.path.join(util.GetUnittestDataDir(),
                                'test_simple_one_page_set.py')
    test_pps_2_dir = os.path.join(util.GetUnittestDataDir(),
                                'test_simple_two_page_set.py')
    pps1 = page_set.PageSet.FromFile(test_pps_1_dir)
    pps2 = page_set.PageSet.FromFile(test_pps_2_dir)

    self.assertEqual('TestSimpleOnePageSet', pps1.__class__.__name__)
    self.assertEqual('TestSimpleTwoPageSet', pps2.__class__.__name__)

  def testPageFilePath(self):
    test_pps_dir = os.path.join(util.GetUnittestDataDir(), 'test_page_set.py')
    pps = page_set.PageSet.FromFile(test_pps_dir)
    internal_page = pps.pages[1]
    external_page = pps.pages[2]
    self.assertEqual(
      os.path.normpath(os.path.join(
        util.GetUnittestDataDir(), 'bar.html')), internal_page.file_path)
    self.assertEqual(
      os.path.normpath(os.path.join(
        util.GetUnittestDataDir(), 'pages/foo.html')), external_page.file_path)

  def testCloudBucket(self):
    blank_ps = page_set.PageSet()
    expected_bucket = None
    self.assertEqual(blank_ps.bucket, expected_bucket)

    public_ps = page_set.PageSet(bucket=page_set.PUBLIC_BUCKET)
    expected_bucket = cloud_storage.PUBLIC_BUCKET
    self.assertEqual(public_ps.bucket, expected_bucket)

    partner_ps = page_set.PageSet(bucket=page_set.PARTNER_BUCKET)
    expected_bucket = cloud_storage.PARTNER_BUCKET
    self.assertEqual(partner_ps.bucket, expected_bucket)

    internal_ps = page_set.PageSet(bucket=page_set.INTERNAL_BUCKET)
    expected_bucket = cloud_storage.INTERNAL_BUCKET
    self.assertEqual(internal_ps.bucket, expected_bucket)

    self.assertRaises(ValueError, page_set.PageSet, bucket='garbage_bucket')

  def testFormingPageSetFromSubPageSet(self):
    page_set_a = page_set.PageSet()
    pages = [
        page.Page('http://foo.com', page_set_a),
        page.Page('http://bar.com', page_set_a),
        ]
    for p in pages:
      page_set_a.AddPage(p)

    # Form page_set_b from sub page_set_a.
    page_set_b = page_set.PageSet()
    for p in pages:
      p.TransferToPageSet(page_set_b)
    page_set_b.AddPage(page.Page('http://baz.com', page_set_b))
    self.assertEqual(0, len(page_set_a.pages))
    self.assertEqual(
        set(['http://foo.com', 'http://bar.com', 'http://baz.com']),
        set(p.url for p in page_set_b.pages))
    for p in page_set_b.pages:
      self.assertIs(page_set_b, p.page_set)
