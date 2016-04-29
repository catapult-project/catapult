# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generates reports base on bisect result data."""

import copy
import math

_CONFIDENCE_THRESHOLD = 99.5

_BISECT_REPORT_TEMPLATE = """
===== BISECT JOB RESULTS =====
Status: %(status)s

%(result)s

Bisect job ran on: %(bisect_bot)s
Bug ID: %(bug_id)s

Test Command: %(command)s
Test Metric: %(metric)s
Relative Change: %(change)s
Score: %(score)s

Buildbot stdio: %(buildbot_log_url)s
Job details: %(issue_url)s

"""

_RESULTS_REVISION_INFO = """
===== SUSPECTED CL(s) =====
Subject : %(subject)s
Author  : %(author)s
Commit description:
  %(commit_info)s
Commit  : %(cl)s
Date    : %(cl_date)s

"""

_ABORTED_REASON_TEMPLATE = """
=== Bisection aborted ===
The bisect was aborted because %s
Please contact the the team (see below) if you believe this is in error.
"""

_WARNINGS_TEMPLATE = """
=== Warnings ===
The following warnings were raised by the bisect job:

 * %s
"""

_REVISION_TABLE_TEMPLATE = """
===== TESTED REVISIONS =====
%(table)s"""

_RESULTS_THANK_YOU = """
| O O | Visit http://www.chromium.org/developers/speed-infra/perf-bug-faq
|  X  | for more information addressing perf regression bugs. For feedback,
| / \\ | file a bug with component Tests>AutoBisect.  Thank you!"""

_REPORT_BAD_BISECT_TEMPLATE = """
Not what you expected? We'll investigate and get back to you!
  https://chromeperf.appspot.com/bad_bisect?try_job_id=%s
"""


def GetReport(try_job_entity):
  """Generates a report for bisect results.

  This was ported from recipe_modules/auto_bisect/bisect_results.py.

  Args:
    try_job_entity: A TryJob entity.

  Returns:
    Bisect report string.
  """
  results_data = copy.deepcopy(try_job_entity.results_data)
  if not results_data:
    return ''
  result = ''
  if results_data.get('aborted_reason'):
    result += _ABORTED_REASON_TEMPLATE % results_data['aborted_reason']

  if results_data.get('warnings'):
    warnings = '\n'.join(results_data['warnings'])
    result += _WARNINGS_TEMPLATE % warnings

  if results_data.get('culprit_data'):
    result += _RESULTS_REVISION_INFO % results_data['culprit_data']

  if results_data.get('revision_data'):
    result += _RevisionTable(results_data)

  results_data['result'] = result
  report = _BISECT_REPORT_TEMPLATE % results_data
  if try_job_entity.bug_id > 0:
    report += _REPORT_BAD_BISECT_TEMPLATE % try_job_entity.key.id()
  report += _RESULTS_THANK_YOU
  return report


def _MakeLegacyRevisionString(r):
  result = 'chromium@' + str(r.get('commit_pos', 'unknown'))
  if r.get('depot_name', 'chromium') != 'chromium':
    result += ',%s@%s' % (r['depot_name'], r.get('deps_revision', 'unknown'))
  return result


def _RevisionTable(results_data):
  is_return_code = results_data.get('test_type') == 'return_code'
  culprit_commit_hash = None
  if 'culprit_data' in results_data and results_data['culprit_data']:
    culprit_commit_hash = results_data['culprit_data']['cl']

  def RevisionRow(r):
    result = [
        r.get('revision_string', _MakeLegacyRevisionString(r)),
        _FormatNumber(r['mean_value']),
        _FormatNumber(r['std_dev']),
        _FormatNumber(len(r['values'])),
        r['result'],
        '<--' if r['commit_hash'] == culprit_commit_hash  else '',
    ]
    return map(str, result)
  revision_rows = [RevisionRow(r) for r in results_data['revision_data']]

  headers_row = [[
      'Revision',
      'Mean' if not is_return_code else 'Exit Code',
      'Std Dev',
      'N',
      'Good?',
      '',
  ]]
  all_rows = headers_row + revision_rows
  return _REVISION_TABLE_TEMPLATE % {'table': _PrettyTable(all_rows)}


def _FormatNumber(x):
  if x is None:
    return 'N/A'
  if isinstance(x, int) or x == 0:
    return str(x)

  if x >= 10**5:
    # It's a little awkward to round 123456789.987 to 123457000.0,
    # so just make it 123456790.
    return str(int(round(x)))
  # Round to 6 significant figures.
  return str(round(x, 5-int(math.floor(math.log10(abs(x))))))


def _PrettyTable(data):
  column_lengths = [max(map(len, c)) for c in zip(*data)]
  formatted_rows = []
  for row in data:
    formatted_elements = []
    for element_length, element in zip(column_lengths, row):
      formatted_elements.append(element.ljust(element_length))
    formatted_rows.append('  '.join(formatted_elements).strip())
  return '\n'.join(formatted_rows)
