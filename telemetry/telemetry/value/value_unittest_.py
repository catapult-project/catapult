# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set =  page_set.PageSet.FromDict({
      "description": "hello",
      "archive_path": "foo.wpr",
      "pages": [
        {"url": "http://www.bar.com/"},
        {"url": "http://www.baz.com/"},
        {"url": "http://www.foo.com/"}
        ]
      }, os.path.dirname(__file__))

  @property
  def pages(self):
    return self.page_set.pages

class ValueTest(TestBase):
  def testCompat(self):
    page0 = self.pages[0]
    page1 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False)
    b = value.Value(page1, 'x', 'unit', important=False)
    self.assertTrue(b.IsMergableWith(a))

  def testIncompat(self):
    page0 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False)
    b = value.Value(page0, 'x', 'incompatUnit', important=False)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False)
    b = value.Value(page0, 'x', 'unit', important=True)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False)
    b = value.ScalarValue(page0, 'x', 'unit', 3, important=True)
    self.assertFalse(b.IsMergableWith(a))
