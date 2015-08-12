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
    r'^dashboard[\\\/]third_party[\\\/].*',
    r'^experimental[\\\/]heatmap[\\\/].*',
    r'^perf_insights[\\\/]test_data[\\\/].*',
    r'^perf_insights[\\\/]third_party[\\\/].*',
    r'^third_party[\\\/].*',
    r'^tracing[\\\/]\.allow-devtools-save$',
    r'^tracing[\\\/]bower\.json$',
    r'^tracing[\\\/]\.bowerrc$',
    r'^tracing[\\\/]examples[\\\/]string_convert\.js$',
    r'^tracing[\\\/]test_data[\\\/].*',
    r'^tracing[\\\/]third_party[\\\/].*',
)


def GetPreferredTryMasters(project, change):  # pylint: disable=unused-argument
  return {
      'tryserver.client.catapult': {
          'Catapult Linux Tryserver': {'defaulttests'},
          'Catapult Mac Tryserver': {'defaulttests'},
          'Catapult Windows Tryserver': {'defaulttests'},
      }
  }


def CheckChangeLogBug(input_api, output_api):
  if input_api.change.BUG is None or re.match(
      '(\#\d+)(,\s*\#\d+)*$', input_api.change.BUG):
    return []
  return [output_api.PresubmitError(
      ('Invalid bug "%s". BUG= should either not be present or start with # '
       'for a github issue.' % input_api.change.BUG))]


def CheckChange(input_api, output_api):
  results = []
  try:
    sys.path += [input_api.PresubmitLocalPath()]
    from build import js_checks
    results += input_api.canned_checks.PanProjectChecks(
        input_api, output_api, excluded_paths=_EXCLUDED_PATHS)
    results += input_api.canned_checks.RunPylint(
        input_api, output_api, black_list=_EXCLUDED_PATHS)
    results += CheckChangeLogBug(input_api, output_api)
    results += js_checks.RunChecks(input_api, output_api)
  finally:
    sys.path.remove(input_api.PresubmitLocalPath())
  return results


def CheckChangeOnUpload(input_api, output_api):
  return CheckChange(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CheckChange(input_api, output_api)
