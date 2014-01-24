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

class ModuleIntegrationTests(unittest.TestCase):
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
      x_module = loader.load_module('x')

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
      my_module = loader.load_module(module_name = 'src.my_module')
      assert [x.name for x in my_module.dependent_modules] == ['base.foo']
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
      my_module = loader.load_module(module_name='z.foo')
      self.assertEquals(1, len(my_module.dependent_raw_scripts))

      rs = my_module.dependent_raw_scripts[0]
      self.assertEquals('hello', rs.contents)
      self.assertEquals('/x/raw/bar.js', rs.filename)


  def testModulesThatAreDirectores(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict';""")

    loader = resource_loader.ResourceLoader(['/x'], [])
    with fs:
      foo_module = loader.load_module(module_name = 'foo')
      self.assertEquals('foo', foo_module.name)
      self.assertEquals('/x/foo/__init__.js', foo_module.filename)

  def testModulesThatAreDirectoresLoadedWithAbsoluteName(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict';""")

    loader = resource_loader.ResourceLoader(['/x'], [])
    with fs:
      foo_module = loader.load_module(module_filename = '/x/foo/__init__.js')
      self.assertEquals('foo', foo_module.name)
      self.assertEquals('/x/foo/__init__.js', foo_module.filename)

  def testExceptionRaisedWhenOldStyleModuleRootExists(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict';""")
    fs.AddFile('/x/foo.js', """'use strict';""")

    loader = resource_loader.ResourceLoader(['/x'], [])
    with fs:
      self.assertRaises(module.DepsException,
          lambda: loader.load_module(module_name = 'foo'))
      self.assertRaises(module.DepsException,
          lambda: loader.load_module(module_filename = '/x/foo/__init__.js'))
