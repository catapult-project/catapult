# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from tvcm import project as project_module
from tvcm import module_test_case

def load_tests(loader, tests, pattern):
  tvcm_project = project_module.Project()
  suite = unittest.TestSuite()
  suite.addTest(module_test_case.DiscoverTestsInModule(
      tvcm_project, tvcm_project.tvcm_path))
  return suite
