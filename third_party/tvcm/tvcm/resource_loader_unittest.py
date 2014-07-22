#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for resource_loader."""

import os
import unittest

from tvcm import module
from tvcm import resource_loader
from tvcm import project as project_module


class ResourceLoaderTest(unittest.TestCase):

  def test_basic(self):
    tvcm_project = project_module.Project()
    loader = resource_loader.ResourceLoader(tvcm_project)
    guid_module = loader.LoadModule(module_name='tvcm')
    self.assertTrue(os.path.samefile(
        guid_module.filename,
        os.path.join(tvcm_project.tvcm_src_path, 'tvcm.html')))
    expected_contents = ''
    with open(os.path.join(tvcm_project.tvcm_src_path, 'tvcm.html')) as f:
      expected_contents = f.read()
    self.assertEquals(guid_module.contents, expected_contents)

if __name__ == '__main__':
  unittest.main()
