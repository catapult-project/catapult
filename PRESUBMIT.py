# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for catapult.

See https://www.chromium.org/developers/how-tos/depottools/presubmit-scripts
for more details about the presubmit API built into depot_tools.
"""
import re
import sys

_EXCLUDED_PATHS = (
    r'(.*[\\/])?\.git[\\/].*',
    r'.+\.png$',
    r'.+\.svg$',
    r'.+\.skp$',
    r'.+\.gypi$',
    r'.+\.gyp$',
    r'.+\.gn$',
    r'.*\.gitignore$',
    r'.*codereview.settings$',
    r'.*AUTHOR$',
    r'^CONTRIBUTORS\.md$',
    r'.*LICENSE$',
    r'.*OWNERS$',
    r'.*README\.md$',
    r'^dashboard[\\/]dashboard[\\/]templates[\\/].*',
    r'^experimental[\\/]heatmap[\\/].*',
    r'^perf_insights[\\/]test_data[\\/].*',
    r'^perf_insights[\\/]third_party[\\/].*',
    r'^third_party[\\/].*',
    r'^tracing[\\/]\.allow-devtools-save$',
    r'^tracing[\\/]bower\.json$',
    r'^tracing[\\/]\.bowerrc$',
    r'^tracing[\\/]tracing_examples[\\/]string_convert\.js$',
    r'^tracing[\\/]test_data[\\/].*',
    r'^tracing[\\/]third_party[\\/].*',
    r'^telemetry[\\/]support[\\/]html_output[\\/]results-template.html',
)


_CATAPULT_BUG_ID_RE = re.compile(r'#[1-9]\d*')
_RIETVELD_BUG_ID_RE = re.compile(r'[1-9]\d*')
_RIETVELD_REPOSITORY_NAMES = frozenset({'chromium', 'v8'})


def GetPreferredTryMasters(project, change):
  return {
      'tryserver.client.catapult': {
          'Catapult Android Tryserver': {'defaulttests'},
          'Catapult Linux Tryserver': {'defaulttests'},
          'Catapult Mac Tryserver': {'defaulttests'},
          'Catapult Windows Tryserver': {'defaulttests'},
      }
  }


def CheckChangeLogBug(input_api, output_api):
  # Show a presubmit message if there is no BUG= line.
  if input_api.change.BUG is None:
    return [output_api.PresubmitNotifyResult(
        'If this change has associated Catapult and/or Rietveld bug(s), add a '
        '"BUG=<bug>(, <bug>)*" line to the patch description where <bug> can '
        'be one of the following: catapult:#NNNN, ' +
        ', '.join('%s:NNNNNN' % n for n in _RIETVELD_REPOSITORY_NAMES) + '.')]

  # Throw a presubmit error if the BUG= line is provided but empty.
  if input_api.change.BUG.strip() == '':
    return [output_api.PresubmitError(
        'Empty BUG= line. Either remove it, or, preferably, change it to '
        '"BUG=<bug>(, <bug>)*" where <bug> can be one of the following: ' +
        'catapult:#NNNN, ' +
        ', '.join('%s:NNNNNN' % n for n in _RIETVELD_REPOSITORY_NAMES) + '.')]

  # Check that each bug in the BUG= line has the correct format.
  error_messages = []
  catapult_bug_provided = False
  append_repository_order_error = False

  for index, bug in enumerate(input_api.change.BUG.split(',')):
    if index > 0:
      bug = bug.lstrip()  # Allow spaces after commas.

    # Check if the bug can be split into a repository name and a bug ID (e.g.
    # 'catapult:#1234' -> 'catapult' and '#1234').
    bug_parts = bug.split(':')
    if len(bug_parts) != 2:
      error_messages.append('Invalid bug "%s". Bugs should be provided in the '
                            '"<repository-name>:<bug-id>" format.' % bug)
      continue
    repository_name, bug_id = bug_parts

    if repository_name == 'catapult':
      if not _CATAPULT_BUG_ID_RE.match(bug_id):
        error_messages.append('Invalid bug "%s". Bugs in the Catapult '
                              'repository should be provided in the '
                              '"catapult:#NNNN" format.' % bug)
      catapult_bug_provided = True
    elif repository_name in _RIETVELD_REPOSITORY_NAMES:
      if not _RIETVELD_BUG_ID_RE.match(bug_id):
        error_messages.append('Invalid bug "%s". Bugs in the Rietveld %s '
                              'repository should be provided in the '
                              '"%s:NNNNNN" format.' % (bug, repository_name,
                                                       repository_name))
      if catapult_bug_provided:
        append_repository_order_error = True
    else:
      error_messages.append('Invalid bug "%s". Unknown repository "%s".' % (
          bug, repository_name))

  if append_repository_order_error:
    error_messages.append('Please list Rietveld bugs (' +
                          ', '.join('%s:NNNNNN' % n
                                    for n in _RIETVELD_REPOSITORY_NAMES) +
                          ') before Catapult bugs (catapult:#NNNN) so '
                          'that Rietveld would display them as hyperlinks.')

  return map(output_api.PresubmitError, error_messages)


def CheckChange(input_api, output_api):
  results = []
  try:
    sys.path += [input_api.PresubmitLocalPath()]
    from catapult_build import js_checks
    from catapult_build import html_checks
    from catapult_build import repo_checks
    results += input_api.canned_checks.PanProjectChecks(
        input_api, output_api, excluded_paths=_EXCLUDED_PATHS)
    results += CheckChangeLogBug(input_api, output_api)
    results += js_checks.RunChecks(
        input_api, output_api, excluded_paths=_EXCLUDED_PATHS)
    results += html_checks.RunChecks(
        input_api, output_api, excluded_paths=_EXCLUDED_PATHS)
    results += repo_checks.RunChecks(input_api, output_api)
  finally:
    sys.path.remove(input_api.PresubmitLocalPath())
  return results


def CheckChangeOnUpload(input_api, output_api):
  return CheckChange(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CheckChange(input_api, output_api)
