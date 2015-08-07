# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os
import re

from tracing import tracing_project


def _FindAllFilesRecursive(source_paths):
  assert isinstance(source_paths, list)
  all_filenames = set()
  for source_path in source_paths:
    for dirpath, _, filenames in os.walk(source_path):
      for f in filenames:
        if f.startswith('.'):
          continue
        x = os.path.abspath(os.path.join(dirpath, f))
        all_filenames.add(x)
  return all_filenames

def _IsFilenameATest(x):  # pylint: disable=unused-argument
  if x.endswith('_test.js'):
    return True

  if x.endswith('_test.html'):
    return True

  if x.endswith('_unittest.js'):
    return True

  if x.endswith('_unittest.html'):
    return True

  # TODO(nduca): Add content test?
  return False


class PerfInsightsProject(object):
  catapult_path = os.path.abspath(
      os.path.join(os.path.dirname(__file__), '..', '..'))
  perf_insights_root_path = os.path.abspath(
      os.path.join(catapult_path, 'perf_insights'))
  perf_insights_src_path = os.path.abspath(
      os.path.join(perf_insights_root_path, 'perf_insights'))


  tracing_root_path = os.path.abspath(
      os.path.join(perf_insights_root_path, 'tracing'))
  tracing_third_party_path = os.path.abspath(os.path.join(
      tracing_root_path, 'third_party'))

  catapult_third_party_path = os.path.abspath(os.path.join(
      catapult_path, 'third_party'))


  perf_insights_ui_path = os.path.abspath(
      os.path.join(perf_insights_src_path, 'ui'))

  def __init__(self, *args, **kwargs):
    self.source_paths = []
    self.source_paths.append(self.perf_insights_root_path)

    self.tracing_project = tracing_project.TracingProject()
    self.source_paths.extend(self.tracing_project.source_paths)

  def CreateVulcanizer(self):
    return project_module.Project(self.source_paths)

  def IsD8CompatibleFile(self, filename):
    return not filename.startswith(self.perf_insights_ui_path)

  def FindAllTestModuleRelPaths(self, pred=None):
    if pred is None:
      pred = lambda x: True

    all_filenames = _FindAllFilesRecursive([self.perf_insights_src_path])
    test_module_filenames = [x for x in all_filenames if
                             _IsFilenameATest(x) and pred(x)]
    test_module_filenames.sort()

    return [os.path.relpath(x, self.perf_insights_root_path)
            for x in test_module_filenames]

  def FindAllD8TestModuleRelPaths(self):
    return self.FindAllTestModuleRelPaths(pred=self.IsD8CompatibleFile)
