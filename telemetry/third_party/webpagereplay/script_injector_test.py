#!/usr/bin/env python
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import script_injector
import unittest


LONG_COMMENT = '<!--%s-->' % ('comment,' * 200)
SCRIPT_TO_INJECT = 'var flag = 0;'
EXPECTED_SCRIPT = '<script>%s</script>' % SCRIPT_TO_INJECT
TEXT_HTML = 'text/html'
TEXT_CSS = 'text/css'
APPLICATION = 'application/javascript'

TEMPLATE_HEAD = '<!doctype html><html><head>%s</head><body></body></html>'
TEMPLATE_HTML = '<!doctype html><html>%s<body></body></html>'
TEMPLATE_DOCTYPE = '<!doctype html>%s<body></body>'
TEMPLATE_RAW = '%s<body></body>'
TEMPLATE_COMMENT = '%s<!doctype html>%s<html>%s<head>%s</head></html>'


class ScriptInjectorTest(unittest.TestCase):

  def test_unsupported_content_type(self):
    source = 'abc'
    # CSS.
    new_source, already_injected = script_injector.InjectScript(
        source, TEXT_CSS, SCRIPT_TO_INJECT)
    self.assertEqual(new_source, source)
    self.assertFalse(already_injected)
    # Javascript.
    new_source, already_injected = script_injector.InjectScript(
        source, APPLICATION, SCRIPT_TO_INJECT)
    self.assertEqual(new_source, source)
    self.assertFalse(already_injected)

  def test_empty_content_as_already_injected(self):
    source, already_injected = script_injector.InjectScript(
        '', TEXT_HTML, SCRIPT_TO_INJECT)
    self.assertEqual(source, '')
    self.assertTrue(already_injected)

  def test_already_injected(self):
    source, already_injected = script_injector.InjectScript(
        TEMPLATE_HEAD % EXPECTED_SCRIPT, TEXT_HTML, SCRIPT_TO_INJECT)
    self.assertEqual(source, TEMPLATE_HEAD % EXPECTED_SCRIPT)
    self.assertTrue(already_injected)

  def _assert_successful_injection(self, template):
    source, already_injected = script_injector.InjectScript(
        template % '', TEXT_HTML, SCRIPT_TO_INJECT)
    self.assertEqual(source, template % EXPECTED_SCRIPT)
    self.assertFalse(already_injected)

  def test_normal(self):
    self._assert_successful_injection(TEMPLATE_HEAD)

  def test_no_head_tag(self):
    self._assert_successful_injection(TEMPLATE_HTML)

  def test_no_head_and_html_tag(self):
    self._assert_successful_injection(TEMPLATE_DOCTYPE)

  def test_no_head_html_and_doctype_tag(self):
    self._assert_successful_injection(TEMPLATE_RAW)

  def _assert_successful_injection_with_comment(self, before_doctype,
                                                after_doctype, after_html):
    source, already_injected = script_injector.InjectScript(
        TEMPLATE_COMMENT % (before_doctype, after_doctype, after_html, ''),
        TEXT_HTML, SCRIPT_TO_INJECT)
    expected_source = TEMPLATE_COMMENT % (before_doctype, after_doctype,
                                          after_html, EXPECTED_SCRIPT)
    self.assertEqual(source, expected_source)
    self.assertFalse(already_injected)

  def test_comment_before_doctype(self):
    self._assert_successful_injection_with_comment(LONG_COMMENT, '', '')

  def test_comment_after_doctype(self):
    self._assert_successful_injection_with_comment('', LONG_COMMENT, '')

  def test_comment_after_html(self):
    self._assert_successful_injection_with_comment('', '', LONG_COMMENT)

  def test_all_comments(self):
    self._assert_successful_injection_with_comment(
        LONG_COMMENT, LONG_COMMENT, LONG_COMMENT)


if __name__ == '__main__':
  unittest.main()
