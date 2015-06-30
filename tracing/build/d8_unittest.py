# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from tracing import tracing_project
from tracing.build import d8_compatible_files
from tracing.build import d8_runner


def _GenerateD8TestMethod(test_file_path, search_path):
  def runTest(self):
    exepect_fail = d8_compatible_files.IsTestExpectedToFail(
        test_file_path)
    try:
      d8_runner.ExecuteFile(test_file_path, search_path)
      if exepect_fail:
        self.fail('d8_runner succesfully excecutes %s. You should update '
                  'the d8 compatibiliy list in d8_compatible_files.py' %
                  test_file_path)
    except RuntimeError as e:
      print test_file_path
      if not exepect_fail:
        self.fail('d8_runner fails to excecute %s. Error stack:\n %s' %
                  (test_file_path, e.message))
  return runTest


def _CreateTestCaseInstanceForTestName(file_path, src_path):
  class D8TestCase(unittest.TestCase):
    pass
  test_method = _GenerateD8TestMethod(file_path, src_path)
  test_name = ('D8 Compatibility Check: %s' %
               os.path.relpath(file_path, src_path))
  setattr(D8TestCase, test_name, test_method)
  return D8TestCase(test_name)


def load_tests(loader, standard_tests, pattern):
  del loader, standard_tests, pattern  # unused
  suite = unittest.TestSuite()

  project = tracing_project.TracingProject()
  src_path = project.tracing_src_path
  d8_runnable_files = project.FindAllD8RunnableFiles()

  for file_path in d8_runnable_files:
    suite.addTest(_CreateTestCaseInstanceForTestName(file_path, src_path))
  return suite
