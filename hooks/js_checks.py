# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import re

class JSChecker(object):
  def __init__(self, input_api, file_filter=None):
    self.input_api = input_api
    if file_filter:
      self.file_filter = file_filter
    else:
      self.file_filter = lambda x: True

  def RegexCheck(self, line_number, line, regex, message):
    """Searches for |regex| in |line| to check for a particular style
       violation, returning a message like the one below if the regex matches.
       The |regex| must have exactly one capturing group so that the relevant
       part of |line| can be highlighted. If more groups are needed, use
       "(?:...)" to make a non-capturing group. Sample message:

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
          self.error_highlight(start, length))
    return ''

  def ConstCheck(self, i, line):
    """Check for use of the 'const' keyword."""
    if re.search(r'\*\s+@const', line):
      # Probably a JsDoc line
      return ''

    return self.RegexCheck(i, line, r'(?:^|\s|\()(const)\s',
        'Use var instead of const.')

  def error_highlight(self, start, length):
    """Takes a start position and a length, and produces a row of '^'s to
       highlight the corresponding part of a string.
    """
    return start * ' ' + length * '^'

  def _makeErrorOrWarning(self, error_text, filename):
    return error_text

  def RunChecks(self):
    """Check for violations of the Chromium JavaScript style guide. See
       http://chromium.org/developers/web-development-style-guide#TOC-JavaScript
    """

    import sys
    import warnings
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

      from closure_linter import checker, errors
      from closure_linter.common import errorhandler

    finally:
      sys.path = old_path
      warnings.filters = old_filters

    class ErrorHandlerImpl(errorhandler.ErrorHandler):
      """Filters out errors that don't apply to Chromium JavaScript code."""

      def __init__(self):
        self._errors = []

      def HandleFile(self, filename, first_token):
        self._filename = filename

      def HandleError(self, error):
        if (self._valid(error)):
          error.filename = self._filename
          self._errors.append(error)

      def GetErrors(self):
        return self._errors

      def HasErrors(self):
        return bool(self._errors)

      def _valid(self, error):
        """Check whether an error is valid. Most errors are valid, with a few
           exceptions which are listed here.
        """

        is_grit_statement = bool(
            re.search("</?(include|if)", error.token.line))

        return not is_grit_statement and error.code not in [
            errors.JSDOC_ILLEGAL_QUESTION_WITH_PIPE,
            errors.JSDOC_TAG_DESCRIPTION_ENDS_WITH_INVALID_CHARACTER,
            errors.MISSING_JSDOC_TAG_THIS,
        ]

    results = []

    try:
      affected_files = self.input_api.AffectedFiles(
          file_filter=self.file_filter,
          include_deletes=False)
    except:
      affected_files = []

    def ShouldCheck(f):
      if f.filename.endswith('.js'):
        return True
      if f.filename.endswith('.html'):
        return True
      return False

    affected_js_files = filter(ShouldCheck, affected_files)
    for f in affected_js_files:
      error_lines = []

      for i, line in enumerate(f.contents_as_lines, start=1):
        error_lines += filter(None, [
            self.ConstCheck(i, line),
        ])

      # Use closure_linter to check for several different errors
      import gflags as flags
      flags.FLAGS.strict = True
      error_handler = ErrorHandlerImpl()
      js_checker = checker.JavaScriptStyleChecker(error_handler)
      js_checker.Check(os.path.join(
          self.input_api.repository_root,
          f.filename))

      for error in error_handler.GetErrors():
        highlight = self.error_highlight(
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
            f.filename] + error_lines
        results.append(self._makeErrorOrWarning(
            '\n'.join(error_lines), f.filename))

    return results


def RunChecks(input_api):
  return JSChecker(input_api).RunChecks()
