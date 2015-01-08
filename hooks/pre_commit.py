# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import subprocess
import sys

from trace_viewer import trace_viewer_project
from hooks import pre_commit_checks

class AffectedFile(object):
  def __init__(self, input_api, filename):
    self._filename = filename
    self._input_api = input_api

  def __repr__(self):
    return self._filename

  @property
  def filename(self):
    return self._filename

  @property
  def contents(self):
    with open(self._filename, 'rb') as f:
      return f.read()

  @property
  def new_contents(self):
    with open(self._filename, 'rb') as f:
      return f.read()

class InputAPI(object):
  def __init__(self, tvp):
    self._tvp = tvp
    self.DEFAULT_BLACK_LIST = []

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
  def affected_files(self):
    return self.AffectedFiles(include_deletes=True)

  def AffectedFiles(self,
                    include_deletes=False,
                    file_filter=lambda t: True):
    stdout = self._git(['diff', '--cached', '--name-status'])
    for line in stdout.split('\n'):
      line = line.strip()
      if len(line) == 0:
        continue
      m = re.match('([ACDMRTUXB])\s+(.+)', line)
      if not m:
        import pdb; pdb.set_trace()
        assert m
      filename = m.group(2)
      if m.group(1) == 'D':
        if include_deletes:
          if file_filter(filename):
            yield AffectedFile(self, filename)
      else:
        if file_filter(filename):
          yield AffectedFile(self, filename)


def RunChecks(input_api):
  results = []
  from trace_viewer.build import check_gyp
  gyp_result = check_gyp.GypCheck()
  if len(gyp_result) > 0:
    results += [gyp_result]

  from trace_viewer.build import check_gn
  gn_result = check_gn.GnCheck()
  if len(gn_result) > 0:
    results += [gn_result]

  from tvcm import presubmit_checker
  checker = presubmit_checker.PresubmitChecker(input_api)
  results += checker.RunChecks()

  results += pre_commit_checks.RunChecks(input_api)

  return results


def Main(args):
  tvp = trace_viewer_project.TraceViewerProject()
  input_api = InputAPI(tvp)
  results = RunChecks(input_api)
  print '\n'.join(results)

  if len(results):
    return 255
  return 0
  # TODO(nduca): Add pre-commit checks here.