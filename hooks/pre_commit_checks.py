# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import sys
import time

def _FormatError(msg, files):
  return ('%s in these files:\n' % msg +
      '\n'.join(['  ' + x for x in files])
      )

def _ReportErrorFileAndLine(filename, line_num, dummy_line):
  """Default error formatter for _FindNewViolationsOfRule."""
  return '%s:%s' % (filename, line_num)

def _FindNewViolationsOfRule(callable_rule, input_api,
                             error_formatter=_ReportErrorFileAndLine):
  """Find all newly introduced violations of a per-line rule (a callable).

  Arguments:
    callable_rule: a callable taking a file extension and line of input and
      returning True if the rule is satisfied and False if there was a problem.
    input_api: object to enumerate the affected files.
    source_file_filter: a filter to be passed to the input api.
    error_formatter: a callable taking (filename, line_number, line) and
      returning a formatted error string.

  Returns:
    A list of the newly-introduced violations reported by the rule.
  """
  errors = []
  for f in input_api.AffectedFiles(include_deletes=False):
    # For speed, we do two passes, checking first the full file.  Shelling out
    # to the SCM to determine the changed region can be quite expensive on
    # Win32.  Assuming that most files will be kept problem-free, we can
    # skip the SCM operations most of the time.
    extension = str(f.filename).rsplit('.', 1)[-1]
    if all(callable_rule(extension, line) for line in f.contents_as_lines):
      continue  # No violation found in full text: can skip considering diff.

    for line_num, line in f.changed_lines:
      if not callable_rule(extension, line):
        errors.append(error_formatter(f.filename, line_num, line))

  return errors

def CheckCopyright(input_api):
  project_name = 'Chromium'

  current_year = int(time.strftime('%Y'))
  allow_old_years=True
  if allow_old_years:
    allowed_years = (str(s) for s in reversed(xrange(2006, current_year + 1)))
  else:
    allowed_years = [str(current_year)]
  years_re = '(' + '|'.join(allowed_years) + ')'

  # The (c) is deprecated, but tolerate it until it's removed from all files.
  non_html_license_header = (
      r'.*? Copyright (\(c\) )?%(year)s The %(project)s Authors\. '
        r'All rights reserved\.\n'
      r'.*? Use of this source code is governed by a BSD-style license that '
        r'can be\n'
      r'.*? found in the LICENSE file\.(?: \*/)?\n'
  ) % {
      'year': years_re,
      'project': project_name,
  }
  non_html_license_re = re.compile(non_html_license_header, re.MULTILINE)

  html_license_header = (
      r'^Copyright (\(c\) )?%(year)s The %(project)s Authors\. '
        r'All rights reserved\.\n'
      r'Use of this source code is governed by a BSD-style license that '
        r'can be\n'
      r'found in the LICENSE file\.(?: \*/)?\n'
  ) % {
      'year': years_re,
      'project': project_name,
  }
  html_license_re = re.compile(html_license_header, re.MULTILINE)

  sources = list(input_api.AffectedFiles(include_deletes=False))

  html_sources = [f for f in sources
                  if os.path.splitext(f.filename)[1] == '.html']
  non_html_sources = [f for f in sources
                      if os.path.splitext(f.filename)[1] != '.html']

  results = []
  results += _Check(html_license_re, html_sources)
  results += _Check(non_html_license_re, non_html_sources)
  return results

def _Check(license_re, sources):
  bad_files = []
  for f in sources:
    contents = f.contents
    if not license_re.search(contents):
      bad_files.append(f.filename)
  if bad_files:
    return [_FormatError(
        'License must match:\n%s\n' % license_re.pattern +
        'Found a bad license header',
        bad_files)]
  return []

def CheckLongLines(input_api, maxlen=80):
  """Checks that there aren't any lines longer than maxlen characters in any of
  the text files to be submitted.
  """
  maxlens = {
      '': maxlen,
  }

  # Language specific exceptions to max line length.
  # '.h' is considered an obj-c file extension, since OBJC_EXCEPTIONS are a
  # superset of CPP_EXCEPTIONS.
  CPP_FILE_EXTS = ('c', 'cc')
  CPP_EXCEPTIONS = ('#define', '#endif', '#if', '#include', '#pragma')
  JAVA_FILE_EXTS = ('java',)
  JAVA_EXCEPTIONS = ('import ', 'package ')
  OBJC_FILE_EXTS = ('h', 'm', 'mm')
  OBJC_EXCEPTIONS = ('#define', '#endif', '#if', '#import', '#include',
                     '#pragma')

  LANGUAGE_EXCEPTIONS = [
    (CPP_FILE_EXTS, CPP_EXCEPTIONS),
    (JAVA_FILE_EXTS, JAVA_EXCEPTIONS),
    (OBJC_FILE_EXTS, OBJC_EXCEPTIONS),
  ]

  def no_long_lines(file_extension, line):
    # Check for language specific exceptions.
    if any(file_extension in exts and line.startswith(exceptions)
           for exts, exceptions in LANGUAGE_EXCEPTIONS):
      return True

    file_maxlen = maxlens.get(file_extension, maxlens[''])
    # Stupidly long symbols that needs to be worked around if takes 66% of line.
    long_symbol = file_maxlen * 2 / 3
    # Hard line length limit at 50% more.
    extra_maxlen = file_maxlen * 3 / 2

    line_len = len(line)
    if line_len <= file_maxlen:
      return True

    if '@suppress longLineCheck' in line:
      return True

    if line_len > extra_maxlen:
      return False

    if any((url in line) for url in ('file://', 'http://', 'https://')):
      return True

    if 'url(' in line and file_extension == 'css':
      return True

    if '<include' in line and file_extension in ('css', 'html', 'js'):
      return True

    return re.match(
        r'.*[A-Za-z][A-Za-z_0-9]{%d,}.*' % long_symbol, line)

  def format_error(filename, line_num, line):
    return '%s, line %s, %s chars' % (filename, line_num, len(line))

  errors = _FindNewViolationsOfRule(no_long_lines, input_api,
                                    error_formatter=format_error)
  if errors:
    return [_FormatError(
        'Found lines longer than %s characters' % maxlen,
        errors)]
  else:
    return []

def RunChecks(input_api):
  results = []
  results += CheckCopyright(input_api)
  results += CheckLongLines(input_api)
  return results
