#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the module module, which contains Module and related classes."""

import unittest

from tvcm import fake_fs
from tvcm import module
from tvcm import strip_js_comments
from tvcm import resource_loader

class FlattenTests(unittest.TestCase):
  """Test case for Module.load_and_parse and Module.resolve."""
  def test_module(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/src/x.js', """
'use strict';
base.require('y');
base.require('z');
base.exportTo('xyz', function() { });
""")
    fs.AddFile('/src/y.js', """
'use strict';
base.require('z');
base.exportsTo('xyz', function() { });
""")
    fs.AddFile('/src/z.js', """
'use strict';
base.exportsTo('xyz', function() { });
""")
    with fs:
      loader = resource_loader.ResourceLoader(['/src/'], [])

      x_module = module.Module('x')
      x_module.load_and_parse('/src/x.js')
      x_module.register(loader)
      x_module.resolve(loader)

      self.assertEquals([loader.loaded_scripts['y'],
                         loader.loaded_scripts['z']],
                        x_module.dependent_modules)

      already_loaded_set = set()
      load_sequence = []
      x_module.compute_load_sequence_recursive(load_sequence, already_loaded_set)

      self.assertEquals([loader.loaded_scripts['z'],
                         loader.loaded_scripts['y'],
                         x_module],
                        load_sequence)

  def testBasic(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/src/my_module.js', """
'use strict';
base.require('base.foo');
base.exportTo('foo', function() {
});
""")
    fs.AddFile('/x/base/foo.js', """
'use strict';
base.require('base.foo');
base.exportTo('foo', function() {
});
""");
    loader = resource_loader.ResourceLoader(['/x'], [])
    with fs:
      my_module = module.Module('src.my_module')
      my_module.load_and_parse('/x/src/my_module.js')
      my_module.register(loader)
      my_module.resolve(loader)
      assert my_module.dependent_module_names == ['base.foo']
      assert my_module.dependent_modules[0].name == 'base.foo'

  def testRawScript(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/y/z/foo.js', """
'use strict';
base.requireRawScript('bar.js');
""")
    fs.AddFile('/x/raw/bar.js', 'hello');
    loader = resource_loader.ResourceLoader(['/x/y'], ['/x/raw/'])
    with fs:
      my_module = module.Module('y.z.foo')
      my_module.load_and_parse('/x/y/z/foo.js')
      my_module.register(loader)
      my_module.resolve(loader)
      self.assertEquals(1, len(my_module.dependent_raw_scripts))

      rs = my_module.dependent_raw_scripts[0]
      self.assertEquals('hello', rs.contents)
      self.assertEquals('/x/raw/bar.js', rs.filename)


# This test case tests a protected method.
# pylint: disable=W0212
class ValidateStrictModeTests(unittest.TestCase):
  """Test case for _validate_uses_strict_mode."""

  def test_validate_uses_strict_mode_returns_true(self):
    text = "// blahblahblah\n\n'use strict';\n\nbase.require('dependency1');"
    my_module = module.Module('arbitrary_name')
    stripped_text = strip_js_comments.strip_js_comments(text)
    self.assertIsNone(my_module._validate_uses_strict_mode(stripped_text))

  def test_validate_uses_strict_mode_catches_missing_strict_mode(self):
    text = "// blahblahblah\n\nbase.require('dependency1');"
    my_module = module.Module('arbitrary_name')
    stripped_text = strip_js_comments.strip_js_comments(text)
    self.assertRaises(
        lambda: my_module._validate_uses_strict_mode(stripped_text))


# This test case tests a protected method.
# pylint: disable=W0212
class ParseDefinitionTests(unittest.TestCase):
  """Test case for _parse_definition."""

  def test_parse_definition_populates_resource_name_lists(self):
    # Dependencies to resources can be specified in a my_module "definition",
    # and lists of resource names for the my_module are populated correctly.
    text = (
        "// blahblahblah\n"
        "'use strict';\n"
        "base.require('dependency1');\n"
        "base.require('dependency2');\n"
        "base.requireStylesheet('myStylesheet');\n"
        "base.requireTemplate('myTemplate');\n")
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals(['myStylesheet'], my_module.style_sheet_names)
    self.assertEquals(['myTemplate'], my_module.html_template_names)
    self.assertEquals(['dependency1', 'dependency2'],
                      my_module.dependent_module_names)

  def test_parse_definition_missing_semicolons(self):
    # Semicolons can be omitted after base.require statements.
    text = (
        "// blahblahblah\n"
        "'use strict';\n"
        "base.require('dependency1')\n"
        "base.require('dependency2');\n"
        "base.requireStylesheet('myStylesheet')\n")
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals(['myStylesheet'], my_module.style_sheet_names)
    self.assertEquals(['dependency1', 'dependency2'],
                      my_module.dependent_module_names)

  def test_parse_definition_with_deps_and_stylesheet_swapped(self):
    # The dependencies can be specified in different orders.
    text = (
        "// blahblahblah\n"
        "'use strict';\n"
        "base.require('dependency1');\n"
        "base.requireStylesheet('myStylesheet');\n"
        "base.require('dependency2');\n")
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals(['myStylesheet'], my_module.style_sheet_names)
    self.assertEquals(['dependency1', 'dependency2'],
                      my_module.dependent_module_names)

  def test_parse_empty_definition(self):
    # If there are no base.require statements, the lists of resource names
    # for the my_module are all empty.
    text = "// blahblahblah\n'use strict';"
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals([], my_module.style_sheet_names)
    self.assertEquals([], my_module.dependent_module_names)

  def test_parse_definition_with_commented_out_dependency(self):
    # Commented-out base.require statements don't count.
    text = (
        "// blahblahblah\n"
        "'use strict';\n"
        "base.require('dependency1');\n"
        "//base.require('dependency2');\n")
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals([], my_module.style_sheet_names)
    self.assertEquals(['dependency1'], my_module.dependent_module_names)

  def test_parse_definition_with_multiline_comment_before(self):
    # There can be long comments before the base.require lines.
    text = (
        "// Copyright (c) 2012 The Chromium Authors. All rights reserved.\n"
        "// Use of this source code is governed by a BSD-style license that"
        " can be\n"
        "// found in the LICENSE file.\n\n"
        "'use strict';\n\n"
        "/**\n"
        " * @fileoverview TimelineView visualizes TRACE_EVENT events using\n"
        " * the tracing.TimelineTrackView component and adds in selection\n"
        " * summary and control buttons.\n"
        " */\n"
        "base.requireStylesheet('timeline_view')\n"
        "base.require('timeline_track_view');\n"
        "base.require('timeline_analysis');\n"
        "base.require('overlay');\n"
        "base.require('trace_event_importer');\n"
        "base.require('linux_perf_importer');\n"
        "base.exportsTo('tracing', function() {\n")
    my_module = module.Module('timeline_view')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals(['timeline_view'], my_module.style_sheet_names)
    self.assertEquals(['timeline_track_view',
                       'timeline_analysis',
                       'overlay',
                       'trace_event_importer',
                       'linux_perf_importer'], my_module.dependent_module_names)

  def test_parse_definition_with_definition_in_comments(self):
    # Statements inside multi-line comments are ignored.
    text = (
        "// SomeComment\n"
        "/*\n"
        " * All subclasses should depend on linux_perf_parser, e.g.\n"
        " *\n"
        " * base.require('linux_perf_parser');\n"
        " * base.exportTo('tracing', function() { });\n"
        " *\n"
        " */\n"
        "'use strict';\n"
        "base.require('dependency1');\n"
        "base.require('dependency2');\n")
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals([], my_module.style_sheet_names)
    self.assertEquals(['dependency1', 'dependency2'],
                      my_module.dependent_module_names)

  def test_parse_dependency_with_slashes_throws_error(self):
    # An error should be thrown if a slash is found in a resource name.
    text = "base.require('foo/dependency1')"
    my_module = module.Module('myModule')
    self.assertRaises(module.DepsException,
                      lambda: my_module._parse_definition(text))

  def test_parse_dependency_with_dots_is_okay(self):
    # Module names can contain dots.
    text = "base.require('foo.dependency1')"
    my_module = module.Module('myModule')
    stripped_text = strip_js_comments.strip_js_comments(text)
    my_module._parse_definition(stripped_text)
    self.assertEquals([], my_module.style_sheet_names)
    self.assertEquals(['foo.dependency1'],
                      my_module.dependent_module_names)

if __name__ == '__main__':
  unittest.main()
