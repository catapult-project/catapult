# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from trace_viewer.build import d8_runner
from trace_viewer.build import check_common


class D8RunnerUnittest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.test_data_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'test_data'))

  def GetTestFilePath(self, file_name):
    return os.path.join(self.test_data_dir, file_name)

  def testSimpleJsExecution(self):
    file_path = self.GetTestFilePath('print_file_content.js')
    dummy_test_path = self.GetTestFilePath('dummy_test_file')
    output = d8_runner.ExecuteFile(file_path, search_path=self.test_data_dir,
                                   js_args=[dummy_test_path])
    self.assertTrue(
        'This is file contains only data for testing.\n1 2 3 4' in output)

  def testJsFileLoadHtmlFile(self):
    file_path = self.GetTestFilePath('load_simple_html.js')
    output = d8_runner.ExecuteFile(file_path, search_path=self.test_data_dir)
    expected_output = ('File foo.html is loaded\n'
                       'x = 1\n'
                       "File foo.html's second script is loaded\n"
                       'x = 2\n'
                       'load_simple_html.js is loaded\n')
    self.assertEquals(output, expected_output)

  def testJsFileLoadJsFile(self):
    file_path = self.GetTestFilePath('load_simple_js.js')
    output = d8_runner.ExecuteFile(file_path, search_path=self.test_data_dir)
    expected_output = ('bar.js is loaded\n'
                       'load_simple_js.js is loaded\n')
    self.assertEquals(output, expected_output)

  def testHTMLFileLoadHTMLFile(self):
    file_path = self.GetTestFilePath('load_simple_html.html')
    output = d8_runner.ExecuteFile(
        file_path, search_path=self.test_data_dir)
    expected_output = ('File foo.html is loaded\n'
                       'x = 1\n'
                       "File foo.html's second script is loaded\n"
                       'x = 2\n'
                       'bar.js is loaded\n'
                      'File load_simple_html.html is loaded\n')
    self.assertEquals(output, expected_output)

  def testErrorStackTraceJs(self):
    file_path = self.GetTestFilePath('error_stack_test.js')
    # error_stack_test.js imports load_simple_html.html
    # load_simple_html.html imports foo.html
    # foo.html imports error.js
    # error.js defines maybeRaiseException() method that can raise exception
    # foo.html defines maybeRaiseExceptionInFoo() method that calls
    # maybeRaiseException()
    # Finally, we call maybeRaiseExceptionInFoo() error_stack_test.js
    # Exception log should capture these method calls' stack trace.
    with self.assertRaises(RuntimeError) as context:
      d8_runner.ExecuteFile(file_path, search_path=self.test_data_dir)

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message
    self.assertIn(
      ('error.js:7: Error: Throw ERROR\n'
       "    throw new Error('Throw ERROR');"), exception_message)
    self.assertIn('maybeRaiseException (error.js:7:11)', exception_message)
    self.assertIn('headless_global.maybeRaiseExceptionInFoo (foo.html:14:5)',
                  exception_message)
    self.assertIn('at %s:14:1' % file_path, exception_message)

  def testErrorStackTraceHTML(self):
    file_path = self.GetTestFilePath('error_stack_test.html')
    # error_stack_test.html imports error_stack_test.js
    # error_stack_test.js imports load_simple_html.html
    # load_simple_html.html imports foo.html
    # foo.html imports error.js
    # error.js defines maybeRaiseException() method that can raise exception
    # foo.html defines maybeRaiseExceptionInFoo() method that calls
    # maybeRaiseException()
    # Finally, we call maybeRaiseExceptionInFoo() error_stack_test.js
    # Exception log should capture these method calls' stack trace.
    with self.assertRaises(RuntimeError) as context:
      d8_runner.ExecuteFile(file_path, search_path=self.test_data_dir)

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message
    self.assertIn(
      ('error.js:7: Error: Throw ERROR\n'
       "    throw new Error('Throw ERROR');"), exception_message)

    self.assertIn('maybeRaiseException (error.js:7:11)', exception_message)
    self.assertIn('headless_global.maybeRaiseExceptionInFoo (foo.html:14:5)',
                  exception_message)
    self.assertIn('at error_stack_test.js:14:1', exception_message)
    self.assertIn('at eval (%s:6:1)' % file_path, exception_message)
