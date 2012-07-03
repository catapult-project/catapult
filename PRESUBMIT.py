# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
_EXCLUDED_PATHS = (
)

def _CheckIfAboutTracingIsOutOfdate(input_api, output_api):
  import build.generate_about_tracing_contents as generator
  if generator.is_out_of_date():
    return [output_api.PresubmitError(
        'This change affects module depenencies. You need to run'
        ' ./build/generate_about_tracing_contents.py')]
  return []

def _CommonChecks(input_api, output_api):
  results = []
  results.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api, excluded_paths=_EXCLUDED_PATHS))
  results.extend(_CheckIfAboutTracingIsOutOfdate(input_api, output_api))
  return results


def runWithPrependedPath(prepended_path, fn, *args):
  import sys
  old_path = sys.path

  try:
    sys.path = [prepended_path] + old_path
    return fn(*args)
  finally:
    sys.path = old_path

def CheckChangeOnUpload(input_api, output_api):
  def go():
    results = []
    results.extend(_CommonChecks(input_api, output_api))
    return results
  return runWithPrependedPath(input_api.PresubmitLocalPath(), go)

def CheckChangeOnCommit(input_api, output_api):
  def go():
    results = []
    results.extend(_CommonChecks(input_api, output_api))
    return results
  return runWithPrependedPath(input_api.PresubmitLocalPath(), go)
