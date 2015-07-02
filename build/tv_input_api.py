# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing import tracing_project


class _AffectedFile(object):
  """Thin wrapper around AffectedFile class from depot_tools.

  See tools/depot_tools/presubmit_support.py in the Chromium tree.
  """
  # TODO(petrcermak): Get rid of this class and use the wrapped object directly
  # (https://github.com/google/trace-viewer/issues/932).
  def __init__(self, depot_tools_affected_file):
    self._depot_tools_affected_file = depot_tools_affected_file
    self._cached_contents = None

  def __repr__(self):
    return self.filename

  @property
  def filename(self):
    return self._depot_tools_affected_file.LocalPath()

  @property
  def absolute_path(self):
    return self._depot_tools_affected_file.AbsoluteLocalPath()

  @property
  def contents(self):
    if self._cached_contents is None:
      self._cached_contents = '\n'.join(self.contents_as_lines)
    return self._cached_contents

  @property
  def contents_as_lines(self):
    """Returns an iterator over the lines in the new version of file.

    The new version is the file in the user's workspace, i.e. the "right hand
    side".

    Contents will be empty if the file is a directory or does not exist.
    Note: The carriage returns (LF or CR) are stripped off.
    """
    return self._depot_tools_affected_file.NewContents()

  @property
  def changed_lines(self):
    """Returns a list of tuples (line number, line text) of all new lines.

     This relies on the scm diff output describing each changed code section
     with a line of the form

     ^@@ <old line num>,<old size> <new line num>,<new size> @@$
    """
    return self._depot_tools_affected_file.ChangedContents()


class TvInputAPI(object):
  """Thin wrapper around InputAPI class from depot_tools.

  See tools/depot_tools/presubmit_support.py in the Chromium tree.
  """
  # TODO(petrcermak): Get rid of this class and use the wrapped object directly
  # (https://github.com/google/trace-viewer/issues/932).
  def __init__(self, depot_tools_input_api):
    self._depot_tools_input_api = depot_tools_input_api

  def AffectedFiles(self, *args, **kwargs):
    return map(_AffectedFile,
               self._depot_tools_input_api.AffectedFiles(*args, **kwargs))

  def IsIgnoredFile(self, affected_file):
    if affected_file.filename.endswith('.png'):
      return True

    if affected_file.filename.endswith('.svg'):
      return True

    if affected_file.filename.endswith('.skp'):
      return True

    if (affected_file.filename.endswith('.gypi') or
        affected_file.filename.endswith('.gyp') or
        affected_file.filename.endswith('.gn')):
      return True

    if self.IsThirdParty(affected_file):
      return True

    # Is test data?
    test_data_path = tracing_project.TracingProject.test_data_path
    if affected_file.absolute_path.startswith(test_data_path):
      return True

    if (affected_file.filename.startswith('.gitignore') or
        affected_file.filename.startswith('codereview.settings') or
        affected_file.filename.startswith('tracing/.allow-devtools-save') or
        affected_file.filename.startswith('tracing/AUTHORS') or
        affected_file.filename.startswith('tracing/LICENSE') or
        affected_file.filename.startswith('tracing/OWNERS') or
        affected_file.filename.startswith('tracing/bower.json') or
        affected_file.filename.startswith('tracing/.gitignore') or
        affected_file.filename.startswith('tracing/.bowerrc') or
        affected_file.filename.startswith('tracing/README.md') or
        affected_file.filename.startswith(
            'tracing/examples/string_convert.js')):
      return True

    return False

  def IsThirdParty(self, affected_file):
    return affected_file.filename.startswith('tracing/third_party')
