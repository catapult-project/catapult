#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

import parse_deps
import os

srcdir = os.path.join(os.path.dirname(__file__), '../src')

class JSStripTests(unittest.TestCase):
  def test_tokenize_0(self):
    tokens = list(parse_deps._tokenize_js(''))
    self.assertEquals([], tokens)

  def test_tokenize_nl(self):
    tokens = list(parse_deps._tokenize_js('\n'))
    self.assertEquals(['\n'], tokens)

  def test_tokenize_slashslash_comment(self):
    tokens = list(parse_deps._tokenize_js('A // foo'))
    self.assertEquals(['A ', '//', ' foo'], tokens)

  def test_tokenize_slashslash_comment_then_newline2(self):
    tokens = list(parse_deps._tokenize_js("""A // foo
bar"""
))
    self.assertEquals(['A ', '//', ' foo', '\n', 'bar'], tokens)

  def test_tokenize_cstyle_comment(self):
    tokens = list(parse_deps._tokenize_js("""A /* foo */"""))
    self.assertEquals(['A ', '/*', ' foo ', '*/'], tokens)

  def test_tokenize_cstyle_comment(self):
    tokens = list(parse_deps._tokenize_js("""A /* foo
*bar
*/"""))
    self.assertEquals(['A ', '/*', ' foo', '\n', '*bar', '\n', '*/'], tokens)

  def test_strip_comments(self):
    self.assertEquals('A ', parse_deps._strip_js_comments('A // foo'))

    self.assertEquals('A  b', parse_deps._strip_js_comments('A /* foo */ b'))
    self.assertEquals('A  b', parse_deps._strip_js_comments("""A /* foo
 */ b"""))


class ValidateTests(unittest.TestCase):
  def test_validate_1(self):
    text = """// blahblahblah

'use strict';

base.require('dependency1');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.validate_uses_strict_mode_(stripped_text)

  def test_validate_2(self):
    text = """// blahblahblah

base.require('dependency1');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    self.assertRaises(lambda: module.validate_uses_strict_mode_(stripped_text))

class ParseTests(unittest.TestCase):
  def test_parse_definition_1(self):
    text = """// blahblahblah
'use strict';
base.require('dependency1');
base.require('dependency2');
base.requireStylesheet('myStylesheet');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals(['myStylesheet'], module.style_sheet_names);
    self.assertEquals(['dependency1', 'dependency2'],
                      module.dependent_module_names);

  def test_parse_definition_missing_semis(self):
    text = """// blahblahblah
'use strict';
base.require('dependency1')
base.require('dependency2');
base.requireStylesheet('myStylesheet')
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals(['myStylesheet'], module.style_sheet_names);
    self.assertEquals(['dependency1', 'dependency2'],
                      module.dependent_module_names);

  def test_parse_definition_with_deps_and_stylesheet_swapped(self):
    text = """// blahblahblah
'use strict';
base.require('dependency1');
base.requireStylesheet('myStylesheet');
base.require('dependency2');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals(['myStylesheet'], module.style_sheet_names);
    self.assertEquals(['dependency1', 'dependency2'],
                      module.dependent_module_names);

  def test_parse_empty_definition(self):
    text = """// blahblahblah
'use strict';
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text, decl_required=False)
    self.assertEquals([], module.style_sheet_names);
    self.assertEquals([], module.dependent_module_names);

  def test_parse_definition_3(self):
    text = """// blahblahblah
'use strict';
base.require('dependency1');
//base.require('dependency2');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals([], module.style_sheet_names);
    self.assertEquals(['dependency1'], module.dependent_module_names);

  def test_parse_definition_4(self):
    text = """// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * @fileoverview TimelineView visualizes TRACE_EVENT events using the
 * tracing.TimelineTrackView component and adds in selection summary and
 * control buttons.
 */
base.requireStylesheet('timeline_view')
base.require('timeline_track_view');
base.require('timeline_analysis');
base.require('overlay');
base.require('trace_event_importer');
base.require('linux_perf_importer');
base.exportsTo('tracing', function() {"""

    module = parse_deps.Module('timeline_view')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals(['timeline_view'], module.style_sheet_names);
    self.assertEquals(['timeline_track_view',
                       'timeline_analysis',
                       'overlay',
                       'trace_event_importer',
                       'linux_perf_importer'], module.dependent_module_names);

  def test_parse_definition_with_definition_in_comments(self):
    text = """// SomeComment
/*
 * All subclasses should depend on linux_perf_parser, e.g.
 *
 * base.require('linux_perf_parser');
 * base.exportTo('tracing', function() { });
 *
 */
'use strict';
base.require('dependency1');
base.require('dependency2');
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals([], module.style_sheet_names);
    self.assertEquals(['dependency1', 'dependency2'],
                      module.dependent_module_names);

  def test_parse_dependency_with_slashes(self):
    text = """base.require('foo/dependency1')
"""
    module = parse_deps.Module('myModule')
    self.assertRaises(parse_deps.DepsException,
                      lambda: module.parse_definition_(text))

  def test_parse_dependency_with_dots(self):
    text = """base.require('foo.dependency1')
"""
    module = parse_deps.Module('myModule')
    stripped_text = parse_deps._strip_js_comments(text)
    module.parse_definition_(stripped_text)
    self.assertEquals([], module.style_sheet_names);
    self.assertEquals(['foo.dependency1'],
                      module.dependent_module_names);


class ResourceFinderStub(object):
  def __init__(self):
    self.modules = {}

  def add_module(self, name, filename, contents):
    module = {'filename': filename,
              'contents': contents}
    self.modules[name] = module

  def find_and_load_module(self, current_module, requested_module_name):
    if requested_module_name not in self.modules:
      return None
    return (self.modules[requested_module_name]['filename'],
            self.modules[requested_module_name]['contents'])


x_contents = """
'use strict';
base.require('y');
base.require('z');
base.exportTo('xyz', function() { });
"""

y_contents = """
'use strict';
base.require('z');
base.exportsTo('xyz', function() { });
"""

z_contents = """
'use strict';
base.exportsTo('xyz', function() { });
"""

class FlattenTests(unittest.TestCase):
  def test_module(self):
    resource_finder = ResourceFinderStub()
    resource_finder.add_module('y', 'y.js', y_contents);
    resource_finder.add_module('z', 'z.js', z_contents);

    x_module = parse_deps.Module('x')
    x_module.load_and_parse('x.js', x_contents)

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


class ResourceFinderTest(unittest.TestCase):
  def test_basic(self):

    resource_finder = parse_deps.ResourceFinder(srcdir)
    module = parse_deps.Module('guid')
    module.load_and_parse(os.path.join(srcdir, 'base', 'guid.js'))
    filename, contents = resource_finder.find_and_load_module(module, 'base')

    self.assertTrue(os.path.samefile(filename, os.path.join(srcdir, 'base.js')))
    expected_contents = ''
    with open(os.path.join(srcdir, 'base.js')) as f:
      expected_contents = f.read()
    self.assertEquals(contents, expected_contents)

  def test_dependency_in_subdir(self):
    resource_finder = parse_deps.ResourceFinder(srcdir)
    module = parse_deps.Module('base.guid')
    module.load_and_parse(os.path.join(srcdir, 'base', 'guid.js'))
    filename, contents = resource_finder.find_and_load_module(
        module, 'tracing.tracks.track')

    assert filename

    self.assertTrue(os.path.samefile(filename, os.path.join(
      srcdir, 'tracing', 'tracks', 'track.js')))
    expected_contents = ''
    with open(os.path.join(srcdir, 'tracing', 'tracks', 'track.js')) as f:
      expected_contents = f.read()
    self.assertEquals(contents, expected_contents)


class CalcLoadSequenceTest(unittest.TestCase):
  def test_one_toplevel_nodeps(self):
    load_sequence = parse_deps.calc_load_sequence(
      [os.path.join(srcdir, 'base', 'guid.js')], srcdir)
    name_sequence = [x.name for x in load_sequence]
    self.assertEquals(['base.guid'], name_sequence)

  # Tests that we resolve deps between toplevels.
  def test_calc_load_sequence_two_toplevels(self):
    pass

if __name__ == '__main__':
  unittest.main()
