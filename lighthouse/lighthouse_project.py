# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os


def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)


def UpdateSysPathIfNeeded():
  p = LighthouseProject()

  _AddToPathIfNeeded(p.lighthouse_third_party_path)

  _AddToPathIfNeeded(p.catapult_path)
  _AddToPathIfNeeded(p.tracing_root_path)
  _AddToPathIfNeeded(p.py_vulcanize_path)

  import tracing_project
  tracing_project.UpdateSysPathIfNeeded()


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


class LighthouseProject(object):
  catapult_path = os.path.abspath(
      os.path.join(os.path.dirname(__file__), os.path.pardir))

  lighthouse_root_path = os.path.join(catapult_path, 'lighthouse')
  lighthouse_src_path = os.path.join(
      lighthouse_root_path, 'lighthouse')

  lighthouse_third_party_path = os.path.join(
      lighthouse_root_path, 'third_party')

  tracing_root_path = os.path.join(catapult_path, 'tracing')

  py_vulcanize_path = os.path.join(catapult_path, 'third_party', 'py_vulcanize')

  def __init__(self):  # pylint: disable=unused-argument
    self._source_paths = None

  @property
  def source_paths(self):
    # We lazily init of source_paths because for lighthouse_project's
    # UpdateSysPathIfNeeded to run, the LighthouseProject must be __init__'d,
    # because thats where we centralize the various directory names.
    # And, for source_paths to be set up, we need the UpdateSysPathIfNeeded to
    # have run! We use laziness to resolve this cyclic dependency.
    if self._source_paths is None:
      self._source_paths = []
      self._source_paths.append(self.lighthouse_root_path)

      import tracing_project as tracing_project_module
      tracing_project = tracing_project_module.TracingProject()
      self._source_paths.extend(tracing_project.source_paths)

    return self._source_paths

  def GetAbsPathFromHRef(self, href):
    for source_path in self.source_paths:
      candidate = os.path.abspath(os.path.join(source_path, href[1:]))
      if os.path.exists(candidate):
        return candidate
    return None

  def CreateVulcanizer(self):
    from py_vulcanize import project as project_module
    return project_module.Project(self.source_paths)

  def IsD8CompatibleFile(self, filename):
    _ = filename
    return True

  def FindAllTestModuleRelPaths(self, pred=None):
    if pred is None:
      pred = lambda x: True
    all_filenames = _FindAllFilesRecursive([self.lighthouse_src_path])
    test_module_filenames = [x for x in all_filenames if
                             _IsFilenameATest(x) and pred(x)]
    test_module_filenames.sort()

    return [os.path.relpath(x, self.lighthouse_root_path)
            for x in test_module_filenames]

  def FindAllD8TestModuleRelPaths(self):
    return self.FindAllTestModuleRelPaths(pred=self.IsD8CompatibleFile)
