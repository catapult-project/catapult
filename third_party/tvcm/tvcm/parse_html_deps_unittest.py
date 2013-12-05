#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

import parse_html_deps
import re


class ParseTests(unittest.TestCase):
  def test_parse_empty(self):
    module = parse_html_deps.Module()
    module.parse("")
    self.assertEquals([], module.scripts_external)
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_none(self):
    module = parse_html_deps.Module()
    module.parse(None)
    self.assertEquals([], module.scripts_external)
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_script_src(self):
    html = """<!DOCTYPE html>
              <html>
                <head>
                  <script src="polymer.min.js"></script>
                  <script src="foo.js"></script>
                </head>
                <body>
                </body>
              </html>"""
    module = parse_html_deps.Module()
    module.parse(html)
    self.assertEquals(['polymer.min.js', 'foo.js'], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_link_rel_import(self):
    html = """<!DOCTYPE html>
              <html>
                <head>
                  <link rel="import" href="x-foo.html">
                </head>
                <body>
                </body>
              </html>"""
    module = parse_html_deps.Module()
    module.parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals(['x-foo.html'], module.imports)

  def test_parse_script_inline(self):
    html = """<polymer-element name="tk-element-proto">
                <template>
                </template>
                <script>
                  base.require("foo");
                  base.require('bar');
                </script>
              </polymer-element>"""

    module = parse_html_deps.Module()
    module.parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals(1, len(module.scripts_inline))
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

    val = module.scripts_inline[0]
    val = re.sub(r"\s+", '', val)
    inner_script = """base.require("foo");base.require('bar');"""
    self.assertEquals(inner_script, val)

  def test_parse_link_rel_stylesheet(self):
    html = """<polymer-element ...>
                <template>
                  <link rel="stylesheet" href="frameworkstyles.css">
                </template>
              </polymer-element>"""
    module = parse_html_deps.Module()
    module.parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals(['frameworkstyles.css'], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_style_import(self):
    html = """<polymer-element name="x-blink" ...>
                <template>
                  <style>
                    @import url(awesome.css);
                  </style>
                </template>
              </polymer-element>"""
    module = parse_html_deps.Module()
    module.parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals(['awesome.css'], module.stylesheets)
    self.assertEquals([], module.imports)


if __name__ == '__main__':
  unittest.main()
