# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from telemetry.web_components import web_components_project
from tvcm import module_test_case


def load_tests(_, _2, _3):
  project = web_components_project.WebComponentsProject()
  if os.getenv('NO_TVCM'):
    suite = unittest.TestSuite()
  else:
    suite = module_test_case.DiscoverTestsInModule(
        project,
        project.telemetry_path)
    assert suite.countTestCases() > 0, 'Expected to find at least one test.'
  return suite
