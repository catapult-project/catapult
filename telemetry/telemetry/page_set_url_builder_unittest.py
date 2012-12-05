# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import urlparse

from telemetry import page
from telemetry import page_set_url_builder

class TestPageSetUrlBuilder(unittest.TestCase):
  def testGetUrlBaseDirAndFileForAbsolutePath(self):
    url = 'file:///somedir/otherdir/file.html'
    parsed_url = urlparse.urlparse(url)
    base_dir = 'basedir'
    dirname, filename = page_set_url_builder.GetUrlBaseDirAndFile({}, base_dir,
                                                                  parsed_url)
    self.assertEqual(dirname, 'basedir/somedir/otherdir')
    self.assertEqual(filename, 'file.html')

  def testGetUrlBaseDirAndFileForRelativePath(self):
    url = 'file:///../../otherdir/file.html'
    parsed_url = urlparse.urlparse(url)
    base_dir = 'basedir'
    dirname, filename = page_set_url_builder.GetUrlBaseDirAndFile({}, base_dir,
                                                                  parsed_url)
    self.assertEqual(dirname, 'basedir/../../otherdir')
    self.assertEqual(filename, 'file.html')

  def testGetUrlBaseDirAndFileForUrlBaseDir(self):
    url = 'file:///../../somedir/otherdir/file.html'
    parsed_url = urlparse.urlparse(url)
    base_dir = 'basedir'
    apage = page.Page(url)
    setattr(apage, 'url_base_dir', 'file:///../../somedir/')
    dirname, filename = page_set_url_builder.GetUrlBaseDirAndFile(
        apage, base_dir, parsed_url)
    self.assertEqual(dirname, 'basedir/../../somedir/')
    self.assertEqual(filename, 'otherdir/file.html')
