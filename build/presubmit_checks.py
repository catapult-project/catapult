# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re


def CheckChangeLogBug(input_api, output_api):
  if input_api.change.BUG is None or re.match(
      '(\#\d+)(,\s*\#\d+)*$', input_api.change.BUG):
    return []
  err = output_api.PresubmitError(
      ('Invalid bug "%s". BUG= should either not be present or start with # '
       'for a github issue.' % input_api.change.BUG))
  return [err]


def RunChecks(input_api, output_api, excluded_paths):
  results = []
  results += input_api.canned_checks.PanProjectChecks(
      input_api, output_api, excluded_paths=excluded_paths)
  results += input_api.canned_checks.RunPylint(
      input_api, output_api, black_list=excluded_paths)
  results += CheckChangeLogBug(input_api, output_api)
  return results
