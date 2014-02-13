# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import os

from tvcm import module_test_case
from tvcm import test_runner
from tvcm import project as project_module

class ModuleTestCaseTests(unittest.TestCase):
  def testDiscoverAndRun(self):
    if test_runner.PY_ONLY_TESTS:
      return
    tvcm_project = project_module.Project()
    t = module_test_case.DiscoverTestsInModule(
      tvcm_project, tvcm_project.tvcm_path)
    interesting_t = test_runner.FilterSuite(
      t,
      lambda x: x.id() == 'tvcm.unittest.test_case_test.parseFullyQualifiedName')

    # This test has to manualy call the run and setUp/tearDown methods
    # so that the Python unittest system doesn't suppress the failures.
    interesting_t.setUp()
    try:
      case = list(interesting_t)[0]
      assert case.id() == 'tvcm.unittest.test_case_test.parseFullyQualifiedName'
      case.runTest()
    finally:
      interesting_t.tearDown()
