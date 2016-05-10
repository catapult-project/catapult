# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import sys
import warnings

from py_vulcanize import strip_js_comments

from catapult_build import parse_html


class JSChecker(object):

  def __init__(self, input_api, output_api, file_filter=None):
    self.input_api = input_api
    self.output_api = output_api
    if file_filter:
      self.file_filter = file_filter
    else:
      self.file_filter = lambda x: True

  def RegexCheck(self, line_number, line, regex, message):
    """Searches for |regex| in |line| to check for a style violation.

    The |regex| must have exactly one capturing group so that the relevant
    part of |line| can be highlighted. If more groups are needed, use
    "(?:...)" to make a non-capturing group. Sample message:

    Returns a message like the one below if the regex matches.
       line 6: Use var instead of const.
           const foo = bar();
           ^^^^^
    """
    match = re.search(regex, line)
    if match:
      assert len(match.groups()) == 1
      start = match.start(1)
      length = match.end(1) - start
      return '  line %d: %s\n%s\n%s' % (
          line_number,
          message,
          line,
          _ErrorHighlight(start, length))
    return ''

  def ConstCheck(self, i, line):
    """Checks for use of the 'const' keyword."""
    if re.search(r'\*\s+@const', line):
      # Probably a JsDoc line.
      return ''

    return self.RegexCheck(
        i, line, r'(?:^|\s|\()(const)\s', 'Use var instead of const.')

  def RunChecks(self):
    """Checks for violations of the Chromium JavaScript style guide.

    See:
    http://chromium.org/developers/web-development-style-guide#TOC-JavaScript
    """
    old_path = sys.path
    old_filters = warnings.filters

    try:
      base_path = os.path.abspath(os.path.join(
          os.path.dirname(__file__), '..'))
      closure_linter_path = os.path.join(
          base_path, 'third_party', 'closure_linter')
      gflags_path = os.path.join(
          base_path, 'third_party', 'python_gflags')
      sys.path.insert(0, closure_linter_path)
      sys.path.insert(0, gflags_path)

      warnings.filterwarnings('ignore', category=DeprecationWarning)

      from closure_linter import runner, errors
      from closure_linter.common import errorhandler

    finally:
      sys.path = old_path
      warnings.filters = old_filters

    class ErrorHandlerImpl(errorhandler.ErrorHandler):
      """Filters out errors that don't apply to Chromium JavaScript code."""

      def __init__(self):
        super(ErrorHandlerImpl, self).__init__()
        self._errors = []
        self._filename = None

      def HandleFile(self, filename, _):
        self._filename = filename

      def HandleError(self, error):
        if self._Valid(error):
          error.filename = self._filename
          self._errors.append(error)

      def GetErrors(self):
        return self._errors

      def HasErrors(self):
        return bool(self._errors)

      def _Valid(self, error):
        """Checks whether an error is valid.

        Most errors are valid, with a few exceptions which are listed here.
        """
        if re.search('</?(include|if)', error.token.line):
          return False  # GRIT statement.

        if (error.code == errors.MISSING_SEMICOLON and
            error.token.string == 'of'):
          return False  # ES6 for...of statement.

        if (error.code == errors.LINE_STARTS_WITH_OPERATOR and
            error.token.string == '*'):
          return False  # *[...] syntax

        if (error.code == errors.MISSING_SPACE and
            error.token.string == '['):
          return False  # *[...] syntax

        return error.code not in [
            errors.JSDOC_ILLEGAL_QUESTION_WITH_PIPE,
            errors.MISSING_JSDOC_TAG_THIS,
            errors.MISSING_MEMBER_DOCUMENTATION,
        ]

    results = []

    affected_files = self.input_api.AffectedFiles(
        file_filter=self.file_filter,
        include_deletes=False)

    def ShouldCheck(f):
      if f.LocalPath().endswith('.js'):
        return True
      if f.LocalPath().endswith('.html'):
        return True
      return False

    affected_js_files = filter(ShouldCheck, affected_files)
    for f in affected_js_files:
      error_lines = []

      contents = list(f.NewContents())
      error_lines += CheckStrictMode(
          '\n'.join(contents),
          is_html_file=f.LocalPath().endswith('.html'))

      for i, line in enumerate(contents, start=1):
        error_lines += filter(None, [self.ConstCheck(i, line)])

      # Use closure_linter to check for several different errors.
      import gflags as flags
      flags.FLAGS.strict = True
      error_handler = ErrorHandlerImpl()
      runner.Run(f.AbsoluteLocalPath(), error_handler)

      for error in error_handler.GetErrors():
        highlight = _ErrorHighlight(
            error.token.start_index, error.token.length)
        error_msg = '  line %d: E%04d: %s\n%s\n%s' % (
            error.token.line_number,
            error.code,
            error.message,
            error.token.line.rstrip(),
            highlight)
        error_lines.append(error_msg)

      if error_lines:
        error_lines = [
            'Found JavaScript style violations in %s:' %
            f.LocalPath()] + error_lines
        results.append(
            _MakeErrorOrWarning(self.output_api, '\n'.join(error_lines)))

    return results


def _ErrorHighlight(start, length):
  """Produces a row of '^'s to underline part of a string."""
  return start * ' ' + length * '^'


def _MakeErrorOrWarning(output_api, error_text):
  return output_api.PresubmitError(error_text)


def CheckStrictMode(contents, is_html_file=False):
  statements_to_check = []
  if is_html_file:
    statements_to_check.extend(_FirstStatementsInScriptElements(contents))
  else:
    statements_to_check.append(_FirstStatement(contents))
  error_lines = []
  for s in statements_to_check:
    if s != "'use strict'":
      error_lines.append('Expected "\'use strict\'" as first statement, '
                         'but found "%s" instead.' % s)
  return error_lines


def _FirstStatementsInScriptElements(contents):
  """Returns a list of first statements found in each <script> element."""
  soup = parse_html.BeautifulSoup(contents)
  script_elements = soup.find_all('script', src=None)
  return [_FirstStatement(e.get_text()) for e in script_elements]


def _FirstStatement(contents):
  """Extracts the first statement in some JS source code."""
  stripped_contents = strip_js_comments.StripJSComments(contents).strip()
  matches = re.match('^(.*?);', stripped_contents, re.DOTALL)
  if not matches:
    return ''
  return matches.group(1).strip()


def RunChecks(input_api, output_api, excluded_paths=None):

  def ShouldCheck(affected_file):
    if not excluded_paths:
      return True
    path = affected_file.LocalPath()
    return not any(re.match(pattern, path) for pattern in excluded_paths)

  return JSChecker(input_api, output_api, file_filter=ShouldCheck).RunChecks()
