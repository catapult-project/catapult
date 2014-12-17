#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import unittest
import HTMLParser

from tvcm import parse_html_deps
from tvcm import module as module_module
from tvcm import html_generation_controller


class ParseTests(unittest.TestCase):
  def test_parse_empty(self):
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse("")
    self.assertEquals([], module.scripts_external)
    self.assertEquals([], module.inline_scripts)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_none(self):
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(None)
    self.assertEquals([], module.scripts_external)
    self.assertEquals([], module.inline_scripts)
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)

  def test_parse_script_src(self):
    html = """<!DOCTYPE html>
              <html>
                <head>
                  <script src="polymer.js"></script>
                  <script src="foo.js"></script>
                </head>
                <body>
                </body>
              </html>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(['polymer.js', 'foo.js'], module.scripts_external);
    self.assertEquals([], module.inline_scripts)
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
    self.assertEquals([], module.inline_scripts)
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
    self.assertEquals(1, len(module.inline_scripts))
    self.assertEquals([], module.stylesheets)
    self.assertEquals([], module.imports)
    self.assertFalse(module.has_decl)

    script0 = module.inline_scripts[0]
    val = re.sub(r"\s+", '', script0.contents)
    inner_script = """tvcm.require("foo");tvcm.require('bar');"""
    self.assertEquals(inner_script, val)

    self.assertEquals(1, len(script0.open_tags))
    self.assertEquals('polymer-element', script0.open_tags[0].tag)

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
    self.assertEquals([], module.inline_scripts)
    self.assertEquals(['frameworkstyles.css'], module.stylesheets)
    self.assertEquals([], module.imports)
    self.assertFalse(module.has_decl)

    class Ctl(html_generation_controller.HTMLGenerationController):
      def GetHTMLForStylesheetHRef(self, href):
        if href == "frameworkstyles.css":
          return "<style>FRAMEWORK</style>"
        return None

    gen_html = module.GenerateHTML(Ctl())
    ghtm = """<polymer-element name="hi">
<template>
<style>FRAMEWORK</style>
</template>
</polymer-element>"""
    self.assertEquals(ghtm, gen_html)


  def test_parse_inline_style(self):
    html = """
<style>
  hello
</style>"""
    module = parse_html_deps.HTMLModuleParser().Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

    class Ctl(html_generation_controller.HTMLGenerationController):
      def GetHTMLForInlineStylesheet(self, contents):
        if contents == '\n  hello\n':
          return '\n  HELLO\n'
        return None

    gen_html = module.GenerateHTML(Ctl())
    ghtm = """
<style>
  HELLO
</style>"""
    self.assertEquals(ghtm, gen_html)

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

  def test_html_contents_with_entity(self):
    html = """<a>&rarr;</a>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

  def test_html_content_with_charref(self):
    html = """<a>&#62;</a>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

  def test_html_content_start_end_br(self):
    html = """<a><br /></a>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(html, module.html_contents_without_links_and_script)

  def test_html_content_start_end_img(self):
    html = """<a><img src="foo.png" id="bar" /></a>"""
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

  def test_br_does_not_raise(self):
    html = """<div><br/></div>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)

  def test_p_does_not_raises(self):
    html = """<div></p></div>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)

  def test_link_endlink_does_not_raise(self):
    html = """<link rel="stylesheet" href="foo.css"></link>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)

  def test_link_script_does_not_raise(self):
    html = """<link rel="stylesheet" href="foo.css">
              <script>
              </script>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)

  def test_script_with_script_inside_as_js(self):
    html = """<script>
              var html_lines = [
                '<script>',
                '<\/script>',
              ];
              </script>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)

  def test_invalid_script_escaping_raises(self):
    html = """<script>
              var html_lines = [
                '<script>',
                '< /script>',
              ];
              </script>"""
    parser = parse_html_deps.HTMLModuleParser()
    def DoIt():
      module = parser.Parse(html)
    self.assertRaises(Exception, DoIt)

  def test_script_with_cdata(self):
    html = """<script></h2></script>"""
    parser = parse_html_deps.HTMLModuleParser()
    module = parser.Parse(html)
    self.assertEquals(1, len(module.inline_scripts))
    self.assertEquals('</h2>', module.inline_scripts[0].contents)


if __name__ == '__main__':
  unittest.main()
