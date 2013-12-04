#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from build import strip_js_comments

src_dir = os.path.join(os.path.dirname(__file__), '../src')

class JSStripTests(unittest.TestCase):
  def test_tokenize_0(self):
    tokens = list(strip_js_comments._tokenize_js(''))
    self.assertEquals([], tokens)

  def test_tokenize_nl(self):
    tokens = list(strip_js_comments._tokenize_js('\n'))
    self.assertEquals(['\n'], tokens)

  def test_tokenize_slashslash_comment(self):
    tokens = list(strip_js_comments._tokenize_js('A // foo'))
    self.assertEquals(['A ', '//', ' foo'], tokens)

  def test_tokenize_slashslash_comment_then_newline2(self):
    tokens = list(strip_js_comments._tokenize_js("""A // foo
bar"""
))
    self.assertEquals(['A ', '//', ' foo', '\n', 'bar'], tokens)

  def test_tokenize_cstyle_comment(self):
    tokens = list(strip_js_comments._tokenize_js("""A /* foo */"""))
    self.assertEquals(['A ', '/*', ' foo ', '*/'], tokens)

  def test_tokenize_cstyle_comment(self):
    tokens = list(strip_js_comments._tokenize_js("""A /* foo
*bar
*/"""))
    self.assertEquals(['A ', '/*', ' foo', '\n', '*bar', '\n', '*/'], tokens)

  def test_strip_comments(self):
    self.assertEquals('A ', strip_js_comments.strip_js_comments('A // foo'))

    self.assertEquals('A  b', strip_js_comments.strip_js_comments(
        'A /* foo */ b'))
    self.assertEquals('A  b', strip_js_comments.strip_js_comments("""A /* foo
 */ b"""))
