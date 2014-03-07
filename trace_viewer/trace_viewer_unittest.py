# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from trace_viewer import trace_viewer_project
from tvcm import module_test_case

def load_tests(loader, tests, pattern):
  project = trace_viewer_project.TraceViewerProject()
  return module_test_case.DiscoverTestsInModule(
      project,
      project.src_path)
