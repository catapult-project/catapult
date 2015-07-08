# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys

def RunChecks(depot_tools_input_api, depot_tools_output_api):
  from build import tv_input_api
  input_api = tv_input_api.TvInputAPI(depot_tools_input_api)

  results = []
  from build import presubmit_checks
  results += presubmit_checks.RunChecks(input_api)

  return map(depot_tools_output_api.PresubmitError, results)


def CheckChange(input_api, output_api):
  original_sys_path = sys.path
  try:
    sys.path += [input_api.PresubmitLocalPath()]
    return RunChecks(input_api, output_api)
  finally:
    sys.path = original_sys_path

def CheckChangeOnUpload(input_api, output_api):
  return CheckChange(input_api, output_api)

def CheckChangeOnCommit(input_api, output_api):
  return CheckChange(input_api, output_api)
