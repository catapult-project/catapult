#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

import parse_html_deps
import re


class ParseTests(unittest.TestCase):
  def test_parse_empty(self):
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse("")
    self.assertEquals([], module.scripts_external)
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_none(self):
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(None)
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
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(['polymer.min.js', 'foo.js'], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)
    self.assertTrue(module.has_decl)
    self.assertTrue('DOCTYPE html' not in module.html_contents_without_links_and_script)

  def test_parse_link_rel_import(self):
    html = """<!DOCTYPE html>
              <html>
                <head>
                  <link rel="import" href="x-foo.html">
                </head>
                <body>
                </body>
              </html>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals([], module.stylesheets)
    self.assertEquals(['x-foo.html'], module.imports)
    self.assertTrue(module.has_decl)

  def test_parse_script_inline(self):
    html = """<polymer-element name="tk-element-proto">
                <template>
                </template>
                <script>
                  tvcm.require("foo");
                  tvcm.require('bar');
                </script>
              </polymer-element>"""

    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals(1, len(module.scripts_inline))
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)
    self.assertFalse(module.has_decl)

    val = module.scripts_inline[0]
    val = re.sub(r"\s+", '', val)
    inner_script = """tvcm.require("foo");tvcm.require('bar');"""
    self.assertEquals(inner_script, val)

    assert 'tvcm.require("foo");' not in module.html_contents_without_links_and_script

  def test_parse_script_src_sripping(self):
    html = """
<script src="blah.js"></script>
"""
    module = parse_html_deps.HTMLModuleParser().Parse(html)
    self.assertEquals('\n\n', module.html_contents_without_links_and_script)


  def test_parse_link_rel_stylesheet(self):
    html = """<polymer-element name="hi">
                <template>
                  <link rel="stylesheet" href="frameworkstyles.css">
                </template>
              </polymer-element>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals([], module.scripts_external);
    self.assertEquals([], module.scripts_inline)
    self.assertEquals(['frameworkstyles.css'], module.stylesheets)
    self.assertEquals([], module.imports)
    self.assertFalse(module.has_decl)

  def test_parse_inline_style(self):
    html = """
<style>
  hello
</style>"""
    module = parse_html_deps.HTMLModuleParser().Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

  def test_parse_style_import(self):
    html = """<polymer-element name="x-blink">
                <template>
                  <style>
                    @import url(awesome.css);
                  </style>
                </template>
              </polymer-element>"""
    parser = parse_html_deps.HTMLModuleParser()
    self.assertRaises(lambda: parser.Parse(html))

  def test_html_contents_basic(self):
    html = """<a b="c">d</a>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

  def test_html_contents_with_link_stripping(self):
    html = """<a b="c">d</a>
              <link rel="import" href="x-foo.html">"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals("""<a b="c">d</a>""",
                      module.html_contents_without_links_and_script.strip())

  def test_html_contents_with_style_link_stripping(self):
    html = """<a b="c">d</a>
              <link rel="stylesheet" href="frameworkstyles.css">"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals("""<a b="c">d</a>""",
                      module.html_contents_without_links_and_script.strip())



if __name__ == '__main__':
  unittest.main()
