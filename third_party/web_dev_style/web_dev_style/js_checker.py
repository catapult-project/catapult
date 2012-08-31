# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for Chromium JS resources.

See chrome/browser/resources/PRESUBMIT.py
"""

class JSChecker(object):
  def __init__(self, input_api, output_api, file_filter=None):
    self.input_api = input_api
    self.output_api = output_api
    self.file_filter = file_filter

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
    match = self.input_api.re.search(regex, line)
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

  def ChromeSendCheck(self, i, line):
    """Checks for a particular misuse of 'chrome.send'."""
    return self.RegexCheck(i, line, r"chrome\.send\('[^']+'\s*(, \[\])\)",
        'Passing an empty array to chrome.send is unnecessary.')

  def ConstCheck(self, i, line):
    """Check for use of the 'const' keyword."""
    if self.input_api.re.search(r'\*\s+@const', line):
      # Probably a JsDoc line
      return ''

    return self.RegexCheck(i, line, r'(?:^|\s|\()(const)\s',
        'Use var instead of const.')

  def GetElementByIdCheck(self, i, line):
    """Checks for use of 'document.getElementById' instead of '$'."""
    return self.RegexCheck(i, line, r"(document\.getElementById)\('",
        "Use $('id'), from chrome://resources/js/util.js, instead of "
        "document.getElementById('id'))")

  def error_highlight(self, start, length):
    """Takes a start position and a length, and produces a row of '^'s to
       highlight the corresponding part of a string.
    """
    return start * ' ' + length * '^'

  def _makeErrorOrWarning(self, error_text, filename):
    """Takes a few lines of text indicating a style violation and turns it into
       a PresubmitError (if |filename| is in a directory where we've already
       taken out all the style guide violations) or a PresubmitPromptWarning
       (if it's in a directory where we haven't done that yet).
    """
    # TODO(tbreisacher): Once we've cleaned up the style nits in all of
    # resources/ we can get rid of this function.
    path = self.input_api.os_path
    resources = self.input_api.PresubmitLocalPath()
    dirs = (
        path.join(resources, 'extensions'),
        path.join(resources, 'help'),
        path.join(resources, 'history'),
        path.join(resources, 'net_internals'),
        path.join(resources, 'network_action_predictor'),
        path.join(resources, 'ntp4'),
        path.join(resources, 'options'),
        path.join(resources, 'print_preview'),
        path.join(resources, 'profiler'),
        path.join(resources, 'sync_promo'),
        path.join(resources, 'tracing'),
        path.join(resources, 'uber'),
    )
    if filename.startswith(dirs):
      return self.output_api.PresubmitError(error_text)
    else:
      return self.output_api.PresubmitPromptWarning(error_text)

  def RunChecks(self):
    """Check for violations of the Chromium JavaScript style guide. See
       http://chromium.org/developers/web-development-style-guide#TOC-JavaScript
    """

    import sys
    import warnings
    old_path = sys.path
    old_filters = warnings.filters

    try:
      closure_linter_path = self.input_api.os_path.join(
          self.input_api.change.RepositoryRoot(),
          "third_party",
          "closure_linter")
      gflags_path = self.input_api.os_path.join(
          self.input_api.change.RepositoryRoot(),
          "third_party",
          "python_gflags")

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

      def __init__(self, re):
        self._errors = []
        self.re = re

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
            self.re.search("</?(include|if)", error.token.line))

        return not is_grit_statement and error.code not in [
            errors.COMMA_AT_END_OF_LITERAL,
            errors.JSDOC_ILLEGAL_QUESTION_WITH_PIPE,
            errors.JSDOC_TAG_DESCRIPTION_ENDS_WITH_INVALID_CHARACTER,
            errors.LINE_TOO_LONG,
            errors.MISSING_JSDOC_TAG_THIS,
        ]

    results = []

    affected_files = self.input_api.change.AffectedFiles(
        file_filter=self.file_filter,
        include_deletes=False)
    affected_js_files = filter(lambda f: f.LocalPath().endswith('.js'),
                               affected_files)
    for f in affected_js_files:
      error_lines = []

      # Check for the following:
      # * document.getElementById()
      # * the 'const' keyword
      # * Passing an empty array to 'chrome.send()'
      for i, line in enumerate(f.NewContents(), start=1):
        error_lines += filter(None, [
            self.ChromeSendCheck(i, line),
            self.ConstCheck(i, line),
            self.GetElementByIdCheck(i, line),
        ])

      # Use closure_linter to check for several different errors
      error_handler = ErrorHandlerImpl(self.input_api.re)
      js_checker = checker.JavaScriptStyleChecker(error_handler)
      js_checker.Check(self.input_api.os_path.join(
          self.input_api.change.RepositoryRoot(),
          f.LocalPath()))

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
            f.LocalPath()] + error_lines
        results.append(self._makeErrorOrWarning(
            '\n'.join(error_lines), f.AbsoluteLocalPath()))

    if results:
      results.append(self.output_api.PresubmitNotifyResult(
          'See the JavaScript style guide at '
          'http://www.chromium.org/developers/web-development-style-guide'
          '#TOC-JavaScript and if you have any feedback about the JavaScript '
          'PRESUBMIT check, contact tbreisacher@chromium.org'))

    return results
