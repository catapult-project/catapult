# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Checks to use in PRESUBMIT.py for HTML style violations."""

import os
import re

import bs4

from catapult_build import parse_html


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
  contents = '\n'.join(affected_file.NewContents())
  if _HasHtml5Declaration(contents):
    return []
  error_text = ('In %s:\n' % affected_file.LocalPath() +
                'could not find "<!DOCTYPE html>."')
  return [output_api.PresubmitError(error_text)]


def _HasHtml5Declaration(contents):
  soup = parse_html.BeautifulSoup(contents)
  for item in soup.contents:
    if isinstance(item, bs4.Doctype) and item.lower() == 'html':
      return True
  return False
