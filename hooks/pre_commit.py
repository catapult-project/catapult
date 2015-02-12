# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import subprocess
import sys

from trace_viewer import trace_viewer_project

class AffectedFile(object):
  def __init__(self, input_api, filename):
    self._filename = filename
    self._input_api = input_api
    self._cached_contents = None
    self._cached_changed_contents = None
    self._cached_new_contents = None

  def __repr__(self):
    return self._filename

  @property
  def filename(self):
    return self._filename

  @property
  def contents(self):
    if self._cached_contents is None:
      self._cached_contents = self._input_api._git(
          ['show', ':%s' % self._filename])
    return self._cached_contents

  @property
  def is_added(self):
    return self.fileame in self._input_api.added_files

  @property
  def contents_as_lines(self):
    """Returns an iterator over the lines in the new version of file.

    The new version is the file in the user's workspace, i.e. the "right hand
    side".

    Contents will be empty if the file is a directory or does not exist.
    Note: The carriage returns (LF or CR) are stripped off.
    """
    if self._cached_new_contents is None:
      self._cached_new_contents = self.contents.splitlines()
    return self._cached_new_contents[:]

  @property
  def changed_lines(self):
    """Returns a list of tuples (line number, line text) of all new lines.

     This relies on the scm diff output describing each changed code section
     with a line of the form

     ^@@ <old line num>,<old size> <new line num>,<new size> @@$
    """
    if self._cached_changed_contents is not None:
      return self._cached_changed_contents[:]
    self._cached_changed_contents = []
    line_num = 0

    for line in self.GenerateDiff().splitlines():
      m = re.match(r'^@@ [0-9\,\+\-]+ \+([0-9]+)\,[0-9]+ @@', line)
      if m:
        line_num = int(m.groups(1)[0])
        continue
      if line.startswith('+') and not line.startswith('++'):
        self._cached_changed_contents.append((line_num, line[1:]))
      if not line.startswith('-'):
        line_num += 1
    return self._cached_changed_contents[:]

  def GenerateDiff(self):
    return self._input_api._git(['diff', '--cached', self.filename])


class InputAPI(object):
  def __init__(self, tvp):
    self.DEFAULT_BLACK_LIST = []
    self._tvp = tvp
    self._filename_statuses = None
    self._added_files = None

  def _git(self, args):
    assert isinstance(args, list)
    args = ['git'] + args
    p = subprocess.Popen(
        args,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=self.repository_root)
    res = p.communicate()
    if p.wait() != 0:
      raise Exception(res[1])
    return res[0]

  @property
  def repository_root(self):
    return self._tvp.trace_viewer_path

  @property
  def added_files(self):
    if not self._added_files:
      self._added_files = set()
      for filename, status_char in filename_statuses:
        if status_char == 'A':
          self._added_files.Add(filename)
    return self._added_files

  @property
  def affected_files(self):
    return self.AffectedFiles(include_deletes=True)

  def AffectedFiles(self,
                    include_deletes=False,
                    file_filter=lambda t: True):
    filename_statuses = self._GetFilenameStatuses()
    for filename, status_char in filename_statuses:
      if status_char == 'D':
        if include_deletes:
          if file_filter(filename):
            yield AffectedFile(self, filename)
      else:
        if file_filter(filename):
          yield AffectedFile(self, filename)

  def _GetFilenameStatuses(self):
    if self._filename_statuses != None:
      return self._filename_statuses

    self._filename_statuses = []
    stdout = self._git(['diff', '--cached', '--name-status'])
    for line in stdout.split('\n'):
      line = line.strip()
      if len(line) == 0:
        continue
      m = re.match('([ACDMRTUXB])\s+(.+)', line)
      if not m:
        import pdb; pdb.set_trace()
        assert m

      status_char = m.group(1)
      filename = m.group(2)
      self._filename_statuses.append((filename, status_char))
    return self._filename_statuses


def RunChecks(input_api):
  results = []

  from hooks import pre_commit_checks
  results += pre_commit_checks.RunChecks(input_api)

  from trace_viewer.build import check_gyp
  err = check_gyp.GypCheck()
  if err:
    results += [err]

  from trace_viewer.build import check_gn
  err = check_gn.GnCheck()
  if err:
    results += [err]

  from hooks import js_checks
  results += js_checks.RunChecks(input_api)

  return results


def Main(args):
  tvp = trace_viewer_project.TraceViewerProject()
  input_api = InputAPI(tvp)
  results = RunChecks(input_api)
  print '\n\n'.join(results)

  if len(results):
    return 255
  return 0
