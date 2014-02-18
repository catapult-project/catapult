# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from tvcm import generate
from tvcm import fake_fs
from tvcm import project as project_module
from tvcm import resource_loader

class GenerateTests(unittest.TestCase):
  def testHTMLGeneration(self):
    fs = fake_fs.FakeFS()
    fs.AddFile('/x/foo/my_module.js', """
'use strict';
tvcm.require('foo.other_module');
tvcm.exportTo('foo', function() {
});
""")
    fs.AddFile('/x/foo/other_module.js', """
'use strict';
tvcm.exportTo('foo', function() {
    HelloWorld();
});
""")
    project = project_module.Project(['/x'],
                                     include_tvcm_paths=True)
    with fs:
      load_sequence = project.CalcLoadSequenceForModuleFilenames(
          ['foo/my_module.js'])
      res = generate.GenerateStandaloneHTMLFile(load_sequence, 'Title')
      assert 'HelloWorld();' in res
