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
from tvcm import project as project_module

class ModuleIntegrationTests(unittest.TestCase):
  def test_module(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/src/x.js', """
'use strict';
tvcm.require('y');
tvcm.require('z');
tvcm.exportTo('xyz', function() { });
""")
    fs.AddFile('/src/y.js', """
'use strict';
tvcm.require('z');
tvcm.exportTo('xyz', function() { });
""")
    fs.AddFile('/src/z.js', """
'use strict';
tvcm.exportTo('xyz', function() { });
""")
    with fs:
      project = project_module.Project(['/src/'],
                                       include_tvcm_paths=False)
      loader = resource_loader.ResourceLoader(project)
      x_module = loader.LoadModule('x')

      self.assertEquals([loader.loaded_modules['y'],
                         loader.loaded_modules['z']],
                        x_module.dependent_modules)

      already_loaded_set = set()
      load_sequence = []
      x_module.ComputeLoadSequenceRecursive(load_sequence, already_loaded_set)

      self.assertEquals([loader.loaded_modules['z'],
                         loader.loaded_modules['y'],
                         x_module],
                        load_sequence)

  def testBasic(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/src/my_module.js', """
'use strict';
tvcm.require('tvcm.foo');
tvcm.exportTo('foo', function() {
});
""")
    fs.AddFile('/x/tvcm/foo.js', """
'use strict';
tvcm.require('tvcm.foo');
tvcm.exportTo('foo', function() {
});
""");
    project = project_module.Project(['/x'],
                                     include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      my_module = loader.LoadModule(module_name = 'src.my_module')
      assert [x.name for x in my_module.dependent_modules] == ['tvcm.foo']
      assert my_module.dependent_modules[0].name == 'tvcm.foo'

  def testDepsExceptionContext(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/src/my_module.js', """
'use strict';
tvcm.require('tvcm.foo');
tvcm.exportTo('foo', function() {
});
""")
    fs.AddFile('/x/tvcm/foo.js', """
'use strict';
tvcm.require('missing');
tvcm.exportTo('foo', function() {
});
""");
    project = project_module.Project(['/x'],
                                     include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      exc = None
      try:
        my_module = loader.LoadModule(module_name = 'src.my_module')
        assertFalse('Expected an exception')
      except module.DepsException, e:
        exc = e
      self.assertEquals(
        ['src.my_module', 'tvcm.foo'],
        exc.context)

  def testRawScript(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/y/z/foo.js', """
'use strict';
    tvcm.requireRawScript('bar.js');
""")
    fs.AddFile('/x/raw/bar.js', 'hello');
    project = project_module.Project(['/x/y', '/x/raw/'],
                                     include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      my_module = loader.LoadModule(module_name='z.foo')
      self.assertEquals(1, len(my_module.dependent_raw_scripts))

      rs = my_module.dependent_raw_scripts[0]
      self.assertEquals('hello', rs.contents)
      self.assertEquals('/x/raw/bar.js', rs.filename)


  def testModulesThatAreDirectores(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict'; tvcm.exportTo('foo', function(){});""")

    project = project_module.Project(['/x'], include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      foo_module = loader.LoadModule(module_name = 'foo')
      self.assertEquals('foo', foo_module.name)
      self.assertEquals('/x/foo/__init__.js', foo_module.filename)

  def testModulesThatAreDirectoresLoadedWithAbsoluteName(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict'; tvcm.exportTo('foo', function(){});""")

    project = project_module.Project(['/x'], include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      foo_module = loader.LoadModule(module_filename = '/x/foo/__init__.js')
      self.assertEquals('foo', foo_module.name)
      self.assertEquals('/x/foo/__init__.js', foo_module.filename)

  def testExceptionRaisedWhenOldStyleModuleRootExists(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/__init__.js', """'use strict';""")
    fs.AddFile('/x/foo.js', """'use strict';""")

    project = project_module.Project(['/x'], include_tvcm_paths=False)
    loader = resource_loader.ResourceLoader(project)
    with fs:
      self.assertRaises(module.DepsException,
          lambda: loader.LoadModule(module_name = 'foo'))
      self.assertRaises(module.DepsException,
          lambda: loader.LoadModule(module_filename = '/x/foo/__init__.js'))
