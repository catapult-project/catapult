# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import os

from tvcm import module_test_case
from tvcm import test_runner

class ModuleTestCaseTests(unittest.TestCase):
  def testDiscoverAndRun(self):
    tvcm_base = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))
    third_party = os.path.abspath(os.path.join(
      tvcm_base, '..'))
    t = module_test_case.DiscoverTestsInModule([tvcm_base], [third_party],
                                               tvcm_base)
    interesting_t = test_runner.FilterSuite(
      t,
      lambda x: x.id() == 'base.unittest.test_case_test.parseFullyQualifiedName')

    # This test has to manualy call the run and setUp/tearDown methods
    # so that the Python unittest system doesn't suppress the failures.
    interesting_t.setUp()
    try:
      case = list(interesting_t)[0]
      assert case.id() == 'base.unittest.test_case_test.parseFullyQualifiedName'
      case.runTest()
    finally:
      interesting_t.tearDown()
