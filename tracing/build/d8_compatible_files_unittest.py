# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from tracing import tracing_project
from tracing.build import d8_compatible_files


class TestValidBlackList(unittest.TestCase):
  def runTest(self):
    # Test asserting that the black list of d8 non compatible files is the
    # subset of all files we will run d8_runner against.
    project = tracing_project.TracingProject()
    d8_runnable_files = project.FindAllD8RunnableFiles()
    non_d8_runnable_files = (
        d8_compatible_files.GetD8NonCompatibleFiles().difference(
          d8_runnable_files))
    self.assertFalse(
        non_d8_runnable_files,
        'black list in d8_compatible_files.py contain extra files '
        'that aren\'t covereted by d8_runner: %s' % non_d8_runnable_files)
