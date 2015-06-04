# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from trace_viewer.build import d8_runner
from trace_viewer.build import check_common


class CheckCommonUnittTest(unittest.TestCase):
  def test_filesSortedTest(self):
    error = check_common.CheckListedFilesSorted('foo.gyp', 'tracing_pdf_files',
                                                ['/dir/file.pdf',
                                                 '/dir/another_file.pdf'])
    expected_error = '''In group tracing_pdf_files from file foo.gyp,\
 filenames aren't sorted.

First mismatch:
  /dir/file.pdf

Current listing:
  /dir/file.pdf
  /dir/another_file.pdf

Correct listing:
  /dir/another_file.pdf
  /dir/file.pdf\n\n'''
    assert error == expected_error

  def testSimpleJsExecution(self):
    test_data_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'test_data'))
    js_file_path = os.path.join(test_data_dir, 'print_file_content.js')
    dummy_test_path = os.path.join(test_data_dir, 'dummy_test_file')
    output  = d8_runner.ExcecuteJsFile(js_file_path, js_args=[dummy_test_path])
    self.assertTrue(
        'This is file contains only data for testing.\n1 2 3 4' in output)
