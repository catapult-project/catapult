# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing import tracing_project


class TvInputAPI(object):
  """Thin wrapper around InputAPI class from depot_tools.

  See tools/depot_tools/presubmit_support.py in the Chromium tree.
  """
  # TODO(petrcermak): Get rid of this class and use the wrapped object directly
  # (https://github.com/google/trace-viewer/issues/932).
  def __init__(self, depot_tools_input_api):
    self._depot_tools_input_api = depot_tools_input_api

  def AffectedFiles(self, *args, **kwargs):
    return self._depot_tools_input_api.AffectedFiles(*args, **kwargs)

  def IsIgnoredFile(self, affected_file):
    if affected_file.LocalPath().endswith('.png'):
      return True

    if affected_file.LocalPath().endswith('.svg'):
      return True

    if affected_file.LocalPath().endswith('.skp'):
      return True

    if (affected_file.LocalPath().endswith('.gypi') or
        affected_file.LocalPath().endswith('.gyp') or
        affected_file.LocalPath().endswith('.gn')):
      return True

    if self.IsThirdParty(affected_file):
      return True

    # Is test data?
    test_data_path = tracing_project.TracingProject.test_data_path
    if affected_file.AbsoluteLocalPath().startswith(test_data_path):
      return True

    if (affected_file.LocalPath().startswith('.gitignore') or
        affected_file.LocalPath().startswith('codereview.settings') or
        affected_file.LocalPath().startswith('tracing/.allow-devtools-save') or
        affected_file.LocalPath().startswith('tracing/AUTHORS') or
        affected_file.LocalPath().startswith('tracing/LICENSE') or
        affected_file.LocalPath().startswith('tracing/OWNERS') or
        affected_file.LocalPath().startswith('tracing/bower.json') or
        affected_file.LocalPath().startswith('tracing/.gitignore') or
        affected_file.LocalPath().startswith('tracing/.bowerrc') or
        affected_file.LocalPath().startswith('tracing/README.md') or
        affected_file.LocalPath().startswith(
            'tracing/examples/string_convert.js')):
      return True

    return False

  def IsThirdParty(self, affected_file):
    return affected_file.LocalPath().startswith('tracing/third_party')
