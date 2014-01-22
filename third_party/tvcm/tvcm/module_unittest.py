#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the module module, which contains Module and related classes."""

import unittest

from tvcm import fake_fs
from tvcm import module
from tvcm import strip_js_comments
from tvcm import resource_finder

X_CONTENTS = """
'use strict';
base.require('y');
base.require('z');
base.exportTo('xyz', function() { });
"""

Y_CONTENTS = """
'use strict';
base.require('z');
base.exportsTo('xyz', function() { });
"""

Z_CONTENTS = """
'use strict';
base.exportsTo('xyz', function() { });
"""


class ResourceFinderStub(object):
  """A stub for the ResourceFinder class, used in the test case below."""

  def __init__(self):
    self.modules = {}

  def add_module(self, name, filename, contents):
    """Adds a canned response to be returned by find_and_load_module."""
    my_module_info = {'filename': filename, 'contents': contents}
    self.modules[name] = my_module_info

  # The argument current_module is not used since this is just a stub class.
  # pylint: disable=W0613
  def find_and_load_module(self, current_module, requested_module_name):
    """Returns a (name, contents) pair response that was put in before."""
    if requested_module_name not in self.modules:
      return None
    return (self.modules[requested_module_name]['filename'],
            self.modules[requested_module_name]['contents'])


class FlattenTests(unittest.TestCase):
  """Test case for Module.load_and_parse and Module.resolve."""
  def test_module(self):
    resource_finder = ResourceFinderStub()
    resource_finder.add_module('y', 'y.js', Y_CONTENTS)
    resource_finder.add_module('z', 'z.js', Z_CONTENTS)

    x_module = module.Module('x')
    x_module.load_and_parse('x.js', X_CONTENTS)

    all_resources = {}
    x_module.resolve(all_resources, resource_finder)

    self.assertEquals([all_resources['scripts']['y'],
                       all_resources['scripts']['z']],
                      x_module.dependent_modules)

    already_loaded_set = set()
    load_sequence = []
    x_module.compute_load_sequence_recursive(load_sequence, already_loaded_set)

    self.assertEquals([all_resources['scripts']['z'],
                       all_resources['scripts']['y'],
                       x_module],
                      load_sequence)


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
    my_module._parse_definition(stripped_text, decl_required=False)
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


class FullModuleTest(unittest.TestCase):
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
    finder = resource_finder.ResourceFinder(['/x'])
    all_resources = {}
    all_resources['scripts'] = {}
    with fs:
      my_module = module.Module('src.my_module')
      all_resources['scripts']['src.my_module'] = my_module
      my_module.load_and_parse('/x/src/my_module.js', decl_required=True)
      my_module.resolve(all_resources, finder)
      assert my_module.dependent_module_names == ['base.foo']
      assert my_module.dependent_modules[0].name == 'base.foo'

if __name__ == '__main__':
  unittest.main()
