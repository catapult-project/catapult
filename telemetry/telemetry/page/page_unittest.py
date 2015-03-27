# Copyright 2012 The Chromium Authors. All rights reserved.
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
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('http://www.foo.com/', ps, ps.base_dir))
    ps.AddUserStory(page.Page('http://www.bar.com/', ps, ps.base_dir))

    pages = [ps.pages[0], ps.pages[1]]
    pages.sort()
    self.assertEquals([ps.pages[1], ps.pages[0]],
                      pages)

  def testGetUrlBaseDirAndFileForUrlBaseDir(self):
    base_dir = os.path.dirname(__file__)
    file_path = os.path.join(os.path.dirname(base_dir), 'otherdir', 'file.html')
    ps = page_set.PageSet(file_path=base_dir,
                          serving_dirs=[os.path.join('..', 'somedir', '')])
    ps.AddUserStory(page.Page('file://../otherdir/file.html', ps, ps.base_dir))
    self.assertPathEqual(ps[0].file_path, file_path)

  def testDisplayUrlForHttp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('http://www.foo.com/', ps, ps.base_dir))
    ps.AddUserStory(page.Page('http://www.bar.com/', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'http://www.foo.com/')
    self.assertEquals(ps[1].display_name, 'http://www.bar.com/')

  def testDisplayUrlForHttps(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('http://www.foo.com/', ps, ps.base_dir))
    ps.AddUserStory(page.Page('https://www.bar.com/', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'http://www.foo.com/')
    self.assertEquals(ps[1].display_name, 'https://www.bar.com/')

  def testDisplayUrlForFile(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/foo.html', ps, ps.base_dir))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/bar.html', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'foo.html')
    self.assertEquals(ps[1].display_name, 'bar.html')

  def testDisplayUrlForFilesDifferingBySuffix(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/foo.html', ps, ps.base_dir))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/foo1.html', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'foo.html')
    self.assertEquals(ps[1].display_name, 'foo1.html')

  def testDisplayUrlForFileOfDifferentPaths(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('file://../../somedir/foo.html', ps, ps.base_dir))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/bar.html', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'somedir/foo.html')
    self.assertEquals(ps[1].display_name, 'otherdir/bar.html')

  def testDisplayUrlForFileDirectories(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('file://../../otherdir/foo', ps, ps.base_dir))
    ps.AddUserStory(page.Page('file://../../otherdir/bar', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'foo')
    self.assertEquals(ps[1].display_name, 'bar')

  def testDisplayUrlForSingleFile(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page(
        'file://../../otherdir/foo.html', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'foo.html')

  def testDisplayUrlForSingleDirectory(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page.Page('file://../../otherdir/foo', ps, ps.base_dir))

    self.assertEquals(ps[0].display_name, 'foo')

  def testPagesHaveDifferentIds(self):
    p0 = page.Page("http://example.com")
    p1 = page.Page("http://example.com")
    self.assertNotEqual(p0.id, p1.id)

  def testNamelessPageAsDict(self):
    nameless_dict = page.Page('http://example.com/').AsDict()
    self.assertIn('id', nameless_dict)
    del nameless_dict['id']
    self.assertEquals({
          'url': 'http://example.com/',
        }, nameless_dict)

  def testNamedPageAsDict(self):
    named_dict = page.Page('http://example.com/', name='Example').AsDict()
    self.assertIn('id', named_dict)
    del named_dict['id']
    self.assertEquals({
          'url': 'http://example.com/',
          'name': 'Example'
        }, named_dict)

  def testIsLocal(self):
    p = page.Page('file://foo.html')
    self.assertTrue(p.is_local)

    p = page.Page('chrome://extensions')
    self.assertTrue(p.is_local)

    p = page.Page('about:blank')
    self.assertTrue(p.is_local)

    p = page.Page('http://foo.com')
    self.assertFalse(p.is_local)
