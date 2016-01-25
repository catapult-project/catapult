# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys


def CheckChangeOnUpload(input_api, output_api):
  return _CheckChange(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return _CheckChange(input_api, output_api)


def _CheckChange(input_api, output_api):
  results = []

  original_sys_path = sys.path
  try:
    sys.path += [input_api.PresubmitLocalPath()]
    from tracing_build import check_gypi
    error = check_gypi.GypiCheck()
    if error:
      results.append(output_api.PresubmitError(error))
  finally:
    sys.path = original_sys_path

  results += input_api.RunTests(input_api.canned_checks.GetPylint(
      input_api, output_api, extra_paths_list=_GetPathsToPrepend(input_api),
      pylintrc='../pylintrc'))

  return results


def _GetPathsToPrepend(input_api):
  project_dir = input_api.PresubmitLocalPath()
  catapult_dir = input_api.os_path.join(project_dir, '..')
  return [
      project_dir,

      input_api.os_path.join(catapult_dir, 'third_party', 'mock'),
  ]
