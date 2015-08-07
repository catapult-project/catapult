# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for catapult.

See https://www.chromium.org/developers/how-tos/depottools/presubmit-scripts
for more details about the presubmit API built into depot_tools.
"""
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


def CheckChange(input_api, output_api):
  results = []
  original_sys_path = sys.path
  try:
    sys.path += [input_api.PresubmitLocalPath()]
    from build import presubmit_checks
    results += presubmit_checks.RunChecks(
        input_api, output_api, _EXCLUDED_PATHS)
  finally:
    sys.path = original_sys_path
  return results


def CheckChangeOnUpload(input_api, output_api):
  return CheckChange(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return CheckChange(input_api, output_api)
