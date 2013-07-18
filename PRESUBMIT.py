# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

_EXCLUDED_PATHS = []

_LICENSE_HEADER = (
  r".*? Copyright \(c\) 20\d\d The Chromium Authors\. All rights reserved\."
    "\n"
  r".*? Use of this source code is governed by a BSD-style license that can "
    "be\n"
  r".*? found in the LICENSE file\."
    "\n"
)


def _CommonChecks(input_api, output_api):
  results = []
  results.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api, excluded_paths=_EXCLUDED_PATHS))

  src_dir = os.path.join(input_api.change.RepositoryRoot(), "src")

  def IsResource(maybe_resource):
    f = maybe_resource.AbsoluteLocalPath()
    if not f.endswith(('.css', '.html', '.js')):
      return False
    return True

  from web_dev_style import css_checker, js_checker
  results.extend(css_checker.CSSChecker(input_api, output_api,
                                        file_filter=IsResource).RunChecks())
  results.extend(js_checker.JSChecker(input_api, output_api,
                                      file_filter=IsResource).RunChecks())

  from build import check_gyp
  gyp_result = check_gyp.GypCheck()
  if len(gyp_result) > 0:
    results.extend([output_api.PresubmitError(gyp_result)])

  from build import check_grit
  grit_result = check_grit.GritCheck()
  if len(grit_result) > 0:
    results.extend([output_api.PresubmitError(grit_result)])

  black_list = input_api.DEFAULT_BLACK_LIST
  sources = lambda x: input_api.FilterSourceFile(x, black_list=black_list)
  results.extend(input_api.canned_checks.CheckLicense(
                 input_api, output_api, _LICENSE_HEADER,
                 source_file_filter=sources))
  return results


def GetPathsToPrepend(input_api):
  web_dev_style_path = input_api.os_path.join(
    input_api.change.RepositoryRoot(),
    "third_party",
    "web_dev_style")
  return [input_api.PresubmitLocalPath(), web_dev_style_path]


def RunWithPrependedPath(prepended_path, fn, *args):
  import sys
  old_path = sys.path

  try:
    sys.path = prepended_path + old_path
    return fn(*args)
  finally:
    sys.path = old_path


def CheckChangeOnUpload(input_api, output_api):
  def go():
    results = []
    results.extend(_CommonChecks(input_api, output_api))
    return results
  return RunWithPrependedPath(GetPathsToPrepend(input_api), go)


def CheckChangeOnCommit(input_api, output_api):
  def go():
    results = []
    results.extend(_CommonChecks(input_api, output_api))
    return results
  return RunWithPrependedPath(GetPathsToPrepend(input_api), go)
