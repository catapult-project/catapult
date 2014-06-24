# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

_EXCLUDED_PATHS = []

_LICENSE_HEADER = (
  r".*? Copyright \(c\) 20\d\d The Chromium Authors\. All rights reserved\."
    "\n"
  r".*? Use of this source code is governed by a BSD-style license that can "
    "be\n"
  r".*? found in the LICENSE file\."
    "\n"
)


def _CommonChecksImpl(input_api, output_api):
  results = []
  results += input_api.canned_checks.PanProjectChecks(
      input_api, output_api, excluded_paths=_EXCLUDED_PATHS)

  from trace_viewer import build
  from tvcm import presubmit_checker
  checker = presubmit_checker.PresubmitChecker(input_api, output_api)
  results += checker.RunChecks()


  from trace_viewer.build import check_gyp
  gyp_result = check_gyp.GypCheck()
  if len(gyp_result) > 0:
    results += [output_api.PresubmitError(gyp_result)]

  from trace_viewer.build import check_gn
  gn_result = check_gn.GnCheck()
  if len(gn_result) > 0:
    results += [output_api.PresubmitError(gn_result)]

  black_list = input_api.DEFAULT_BLACK_LIST
  sources = lambda x: input_api.FilterSourceFile(x, black_list=black_list)
  results += input_api.canned_checks.CheckLicense(
      input_api, output_api, _LICENSE_HEADER,
      source_file_filter=sources)

  return results

def _CommonChecks(input_api, output_api):
  tvcm_path = input_api.change.RepositoryRoot()
  sys.path.append(tvcm_path)
  try:
    return _CommonChecksImpl(input_api, output_api)
  finally:
    sys.path.remove(tvcm_path)

def CheckChangeOnUpload(input_api, output_api):
  return _CommonChecks(input_api, output_api)


def CheckChangeOnCommit(input_api, output_api):
  return _CommonChecks(input_api, output_api)
