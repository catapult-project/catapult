# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from py_vulcanize import strip_js_comments
from py_vulcanize import js_utils


class ValidateStrictModeTests(unittest.TestCase):

  def test_ValidateUsesStrictMode_returns_true(self):
    text = "// blahblahblah\n\n'use strict';\n\npy_vulcanize.require('dependency1');"
    stripped_text = strip_js_comments.StripJSComments(text)
    self.assertIsNone(js_utils.ValidateUsesStrictMode('module', stripped_text))

  def test_ValidateUsesStrictModeOneLiner(self):
    text = "'use strict'; py_vulcanize.require('dependency1');"
    stripped_text = strip_js_comments.StripJSComments(text)
    self.assertIsNone(js_utils.ValidateUsesStrictMode('module', stripped_text))

  def test_ValidateUsesStrictMode_catches_missing_strict_mode(self):
    text = "// blahblahblah\n\npy_vulcanize.require('dependency1');"
    stripped_text = strip_js_comments.StripJSComments(text)
    self.assertRaises(
        lambda: js_utils.ValidateUsesStrictMode('module', stripped_text))
