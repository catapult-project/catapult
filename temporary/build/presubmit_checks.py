# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import sys
import time

import checklicenses

from tracing import tracing_project


def _FormatError(msg, files):
  return ('%s in these files:\n' % msg +
          '\n'.join('  ' + x for x in files))


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
    extension = str(f.LocalPath()).rsplit('.', 1)[-1]
    if all(callable_rule(extension, line) for line in f.NewContents()):
      continue  # No violation found in full text: can skip considering diff.

    if tracing_project.TracingProject.IsIgnoredFile(f):
      continue

    for line_num, line in f.ChangedContents():
      if not callable_rule(extension, line):
        errors.append(error_formatter(f.LocalPath(), line_num, line))

  return errors


def CheckCopyright(input_api):
  results = []
  results += _CheckCopyrightThirdParty(input_api)
  results += _CheckCopyrightNonThirdParty(input_api)
  return results


def _CheckCopyrightThirdParty(input_api):
  results = []
  has_third_party_change = any(
      tracing_project.TracingProject.IsThirdParty(f)
      for f in input_api.AffectedFiles(include_deletes=False))
  if has_third_party_change:
    tracing_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..'))
    tracing_third_party = os.path.join(tracing_root, 'tracing', 'third_party')
    has_invalid_license = checklicenses.check_licenses(
        tracing_root, tracing_third_party)
    if has_invalid_license:
      results.append(
          'License check encountered invalid licenses in tracing/third_party/.')
  return results


def _CheckCopyrightNonThirdParty(input_api):
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

  sources = list(s for s in input_api.AffectedFiles(include_deletes=False)
                 if not tracing_project.TracingProject.IsThirdParty(s))

  html_sources = [f for f in sources
                  if os.path.splitext(f.LocalPath())[1] == '.html']
  non_html_sources = [f for f in sources
                      if os.path.splitext(f.LocalPath())[1] != '.html']

  results = []
  results += _Check(input_api, html_license_re, html_sources)
  results += _Check(input_api, non_html_license_re, non_html_sources)
  return results


def _Check(input_api, license_re, sources):
  bad_files = []
  for f in sources:
    if tracing_project.TracingProject.IsIgnoredFile(f):
      continue
    contents = '\n'.join(f.NewContents())
    if not license_re.search(contents):
      bad_files.append(f.LocalPath())
  if bad_files:
    return [_FormatError(
        'License must match:\n%s\n' % license_re.pattern +
        'Found a bad license header',
        bad_files)]
  return []


def CheckLongLines(input_api, maxlen=80):
  """Checks the line length in all text files to be submitted."""
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

def CheckChangeLogBug(input_api):
  results = []
  if input_api.change.BUG is None or re.match('\#\d+$', input_api.change.BUG):
    return []
  return [('Invalid bug "%s". BUG= should either not be present or start'
           ' with # for a github issue.' % input_api.change.BUG)]


def RunChecks(input_api):
  results = []
  results += CheckCopyright(input_api)
  results += CheckLongLines(input_api)
  results += CheckChangeLogBug(input_api)
  return results
