# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.page import page
from telemetry.page import page_set


class TestPage(unittest.TestCase):
  def assertPathEqual(self, path1, path2):
    self.assertEqual(os.path.normpath(path1), os.path.normpath(path2))

  def testFilePathRelative(self):
    apage = page.Page('file://somedir/otherdir/file.html',
                      None, base_dir='basedir')
    self.assertPathEqual(apage.file_path, 'basedir/somedir/otherdir/file.html')

  def testFilePathAbsolute(self):
    apage = page.Page('file:///somedir/otherdir/file.html',
                      None, base_dir='basedir')
    self.assertPathEqual(apage.file_path, '/somedir/otherdir/file.html')

  def testFilePathQueryString(self):
    apage = page.Page('file://somedir/otherdir/file.html?key=val',
                      None, base_dir='basedir')
    self.assertPathEqual(apage.file_path, 'basedir/somedir/otherdir/file.html')

  def testFilePathUrlQueryString(self):
    apage = page.Page('file://somedir/file.html?key=val',
                      None, base_dir='basedir')
    self.assertPathEqual(apage.file_path_url,
                         'basedir/somedir/file.html?key=val')

  def testFilePathUrlTrailingSeparator(self):
    apage = page.Page('file://somedir/otherdir/',
                      None, base_dir='basedir')
    self.assertPathEqual(apage.file_path_url, 'basedir/somedir/otherdir/')
    self.assertTrue(apage.file_path_url.endswith(os.sep) or
                    (os.altsep and apage.file_path_url.endswith(os.altsep)))

  def testSort(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'http://www.foo.com/'},
        {'url': 'http://www.bar.com/'}
        ]
      }, os.path.dirname(__file__))
    pages = [ps.pages[0], ps.pages[1]]
    pages.sort()
    self.assertEquals([ps.pages[1], ps.pages[0]],
                      pages)

  def testGetUrlBaseDirAndFileForUrlBaseDir(self):
    ps = page_set.PageSet.FromDict({
        'description': 'hello',
        'archive_path': 'foo.wpr',
        'serving_dirs': ['../somedir/'],
        'pages': [
          {'url': 'file://../otherdir/file.html'}
        ]}, 'basedir/')
    self.assertPathEqual(ps[0].file_path, 'otherdir/file.html')

  def testDisplayUrlForHttp(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'http://www.foo.com/'},
        {'url': 'http://www.bar.com/'}
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'http://www.foo.com/')
    self.assertEquals(ps[1].display_name, 'http://www.bar.com/')

  def testDisplayUrlForHttps(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'http://www.foo.com/'},
        {'url': 'https://www.bar.com/'}
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'http://www.foo.com/')
    self.assertEquals(ps[1].display_name, 'https://www.bar.com/')

  def testDisplayUrlForFile(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'file://../../otherdir/foo.html'},
        {'url': 'file://../../otherdir/bar.html'},
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'foo.html')
    self.assertEquals(ps[1].display_name, 'bar.html')

  def testDisplayUrlForFilesDifferingBySuffix(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'file://../../otherdir/foo.html'},
        {'url': 'file://../../otherdir/foo1.html'},
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'foo.html')
    self.assertEquals(ps[1].display_name, 'foo1.html')

  def testDisplayUrlForFileOfDifferentPaths(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'file://../../somedir/foo.html'},
        {'url': 'file://../../otherdir/bar.html'},
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'somedir/foo.html')
    self.assertEquals(ps[1].display_name, 'otherdir/bar.html')

  def testDisplayUrlForFileDirectories(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [
        {'url': 'file://../../otherdir/foo/'},
        {'url': 'file://../../otherdir/bar/'},
        ]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'foo')
    self.assertEquals(ps[1].display_name, 'bar')

  def testDisplayUrlForSingleFile(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [{'url': 'file://../../otherdir/foo.html'}]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'foo.html')

  def testDisplayUrlForSingleDirectory(self):
    ps = page_set.PageSet.FromDict({
      'description': 'hello',
      'archive_path': 'foo.wpr',
      'pages': [{'url': 'file://../../otherdir/foo/'}]
      }, os.path.dirname(__file__))
    self.assertEquals(ps[0].display_name, 'foo')
