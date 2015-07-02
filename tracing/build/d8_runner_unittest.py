# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import sys
import unittest

from tracing.build import d8_runner
from tracing.build import check_common


class D8RunnerUnittest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.test_data_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'test_data'))

  def GetTestFilePath(self, file_name):
    return os.path.join(self.test_data_dir, file_name)

  def AssertHasNamedFrame(self, func_name, file_and_linum,
                            exception_message):
    m = re.search('at %s.+\(.*%s.*\)' % (func_name, file_and_linum),
                  exception_message)
    if not m:
      sys.stderr.write('\n=============================================\n')
      msg = "Expected to find %s and %s" % (func_name, file_and_linum)
      sys.stderr.write('%s\n' % msg)
      sys.stderr.write('=========== Begin Exception Message =========\n')
      sys.stderr.write(exception_message);
      sys.stderr.write('=========== End Exception Message =========\n\n')
      self.assertTrue(False, msg)

  def AssertHasFrame(self, file_and_linum,
                     exception_message):
    m = re.search('at .*%s.*' % file_and_linum,
                  exception_message)
    if not m:
      sys.stderr.write('\n=============================================\n')
      msg = "Expected to find %s" % file_and_linum
      sys.stderr.write('%s\n' % msg)
      sys.stderr.write('=========== Begin Exception Message =========\n')
      sys.stderr.write(exception_message);
      sys.stderr.write('=========== End Exception Message =========\n\n')
      self.assertTrue(False, msg)

  def testSimpleJsExecution(self):
    file_path = self.GetTestFilePath('print_file_content.js')
    dummy_test_path = self.GetTestFilePath('dummy_test_file')
    output = d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir],
                                   js_args=[dummy_test_path])
    self.assertTrue(
        'This is file contains only data for testing.\n1 2 3 4' in output)

  def testJsFileLoadHtmlFile(self):
    file_path = self.GetTestFilePath('load_simple_html.js')
    output = d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])
    expected_output = ('File foo.html is loaded\n'
                       'x = 1\n'
                       "File foo.html's second script is loaded\n"
                       'x = 2\n'
                       'load_simple_html.js is loaded\n')
    self.assertEquals(output, expected_output)

  def testJsFileLoadJsFile(self):
    file_path = self.GetTestFilePath('load_simple_js.js')
    output = d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])
    expected_output = ('bar.js is loaded\n'
                       'load_simple_js.js is loaded\n')
    self.assertEquals(output, expected_output)

  def testHTMLFileLoadHTMLFile(self):
    file_path = self.GetTestFilePath('load_simple_html.html')
    output = d8_runner.ExecuteFile(
        file_path, source_paths=[self.test_data_dir])
    expected_output = ('File foo.html is loaded\n'
                       'x = 1\n'
                       "File foo.html's second script is loaded\n"
                       'x = 2\n'
                       'bar.js is loaded\n'
                      'File load_simple_html.html is loaded\n')
    self.assertEquals(output, expected_output)

  def testQuit0Handling(self):
    file_path = self.GetTestFilePath('quit_0_test.js')
    res = d8_runner.RunFile(file_path, source_paths=[self.test_data_dir])
    self.assertEquals(res.returncode, 0)

  def testQuit1Handling(self):
    file_path = self.GetTestFilePath('quit_1_test.js')
    res = d8_runner.RunFile(file_path, source_paths=[self.test_data_dir])
    self.assertEquals(res.returncode, 1)

  def testQuit1Handling(self):
    file_path = self.GetTestFilePath('quit_42_test.js')
    res = d8_runner.RunFile(file_path, source_paths=[self.test_data_dir])
    self.assertEquals(res.returncode, 42)

  def testQuit274Handling(self):
    file_path = self.GetTestFilePath('quit_274_test.js')
    res = d8_runner.RunFile(file_path, source_paths=[self.test_data_dir])
    self.assertEquals(res.returncode, 238)

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
      d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message
    self.assertIn(
      ('error.js:7: Error: Throw ERROR\n'
       "    throw new Error('Throw ERROR');"), exception_message)
    self.AssertHasNamedFrame('maybeRaiseException', 'error.js:7',
                               exception_message)
    self.AssertHasNamedFrame('global.maybeRaiseExceptionInFoo', 'foo.html:13',
                        exception_message)
    self.AssertHasFrame('error_stack_test.js:14', exception_message)
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
      d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message
    self.assertIn(
      ('error.js:7: Error: Throw ERROR\n'
       "    throw new Error('Throw ERROR');"), exception_message)

    self.AssertHasNamedFrame('maybeRaiseException', 'error.js:7',
                             exception_message)
    self.AssertHasNamedFrame('global.maybeRaiseExceptionInFoo', 'foo.html:13',
                             exception_message)
    self.AssertHasFrame('error_stack_test.js:14', exception_message)
    self.AssertHasNamedFrame('eval', 'error_stack_test.html:5',
                             exception_message)

  def testStackTraceOfErroWhenLoadingHTML(self):
    file_path = self.GetTestFilePath('load_error.html')
    with self.assertRaises(RuntimeError) as context:
      d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message

    self.assertIn('Error: /does_not_exist.html not found', exception_message)
    self.AssertHasNamedFrame('eval', 'load_error_2.html:6', exception_message)
    self.AssertHasNamedFrame('eval', 'load_error.html:1', exception_message)

  def testStackTraceOfErroWhenLoadingJS(self):
    file_path = self.GetTestFilePath('load_js_error.html')
    with self.assertRaises(RuntimeError) as context:
      d8_runner.ExecuteFile(file_path, source_paths=[self.test_data_dir])

    # Assert error stack trace contain src files' info.
    exception_message = context.exception.message

    self.assertIn('Error: /does_not_exist.js not found', exception_message)
    self.AssertHasNamedFrame('eval', 'load_js_error_2.html:5',
                             exception_message)
    self.AssertHasNamedFrame('eval', 'load_js_error.html:1',
                             exception_message)

  def testConsolePolyfill(self):
    self.assertEquals(
        d8_runner.ExcecuteJsString('console.log("hello", "world");'),
        'hello world\n')
    self.assertEquals(
        d8_runner.ExcecuteJsString('console.info("hello", "world");'),
        'Info: hello world\n')
    self.assertEquals(
        d8_runner.ExcecuteJsString('console.warn("hello", "world");'),
        'Warning: hello world\n')
    self.assertEquals(
        d8_runner.ExcecuteJsString('console.error("hello", "world");'),
        'Error: hello world\n')
