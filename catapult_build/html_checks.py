# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Checks to use in a PRESUBMIT.py for style violations in HTML files.

See: https://www.chromium.org/developers/how-tos/depottools/presubmit-scripts
"""

import os
import re


def RunChecks(input_api, output_api, excluded_paths=None):

  def ShouldCheck(affected_file):
    path = affected_file.LocalPath()
    if not path.endswith('.html'):
      return False
    if not excluded_paths:
      return True
    return not any(re.match(pattern, path) for pattern in excluded_paths)

  affected_files = input_api.AffectedFiles(
      file_filter=ShouldCheck, include_deletes=False)
  results = []
  for f in affected_files:
    results.extend(CheckDoctype(f, output_api))
  return results


def CheckDoctype(affected_file, output_api):
  lines = list(affected_file.NewContents())
  if lines and lines[0].strip() == '<!DOCTYPE html>':
    return []
  error_text = ('In %s:\n' % affected_file.LocalPath() +
                'The first line must be "<!DOCTYPE html>."')
  return [output_api.PresubmitError(error_text)]

