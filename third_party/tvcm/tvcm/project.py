# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from tvcm import resource as resource_module
from tvcm import parse_deps
from tvcm import resource_loader
from tvcm import js_module

def _FindAllFilesRecursive(source_paths):
  all_filenames = set()
  for source_path in source_paths:
    for dirpath, dirnames, filenames in os.walk(source_path):
      for f in filenames:
        x = os.path.abspath(os.path.join(dirpath, f))
        all_filenames.add(x)
  return all_filenames

def _IsFilenameAJSModule(x):
  if os.path.basename(x).startswith('.'):
    return False
  if os.path.splitext(x)[1] != ".js":
    return False
  with open(x, 'r') as f:
    content = f.read()
  return js_module.IsJSModule(content, text_is_stripped=False)

def _IsFilenameAJSTest(x):
  basename = os.path.basename(x)
  if basename.startswith('.'):
    return False

  if basename.endswith('_test.js'):
    return True

  # TODO(nduca): Add content test?
  return False

def _FindAllJSModuleFilenames(source_paths):
  all_filenames = _FindAllFilesRecursive(source_paths)
  return [x for x in all_filenames if
          _IsFilenameAJSModule(x)]

def _FindTestModuleFilenames(source_paths):
  all_filenames = _FindAllFilesRecursive(source_paths)
  return [x for x in all_filenames if
          _IsFilenameAJSTest(x)]

class Project(object):
  tvcm_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))

  tvcm_src_path = os.path.abspath(os.path.join(
      tvcm_path, 'src'))

  tvcm_third_party_path = os.path.abspath(os.path.join(
      tvcm_path, 'third_party'))

  def __init__(self, source_paths=None, include_tvcm_paths=True):
    """
    source_paths: A list of top-level directories in which modules and raw scripts can be found.
        Module paths are relative to these directories.
    """
    self.source_paths = []
    if include_tvcm_paths:
      self.source_paths += [
          self.tvcm_src_path,
          os.path.join(self.tvcm_third_party_path, 'Promises', 'polyfill', 'src'),
          os.path.join(self.tvcm_third_party_path, 'gl-matrix', 'src'),
          os.path.join(self.tvcm_third_party_path, 'polymer')
      ]
    if source_paths != None:
      self.source_paths += [os.path.abspath(p) for p in source_paths]

  @staticmethod
  def FromDict(d):
    return Project(d['source_paths'])

  def AsDict(self):
    return {'source_paths': self.source_paths}

  def AddSourcePath(self, path):
    self.source_paths.append(path)

  def FindAllTestModuleNames(self, start_path=None):
    if start_path == None:
      test_module_filenames = _FindTestModuleFilenames(self.source_paths)
    else:
      test_module_filenames = _FindTestModuleFilenames([start_path])
    test_module_filenames.sort()

    # Now, need to figure out the relative names now:
    loader = resource_loader.ResourceLoader(self)
    return [loader.find_resource_given_absolute_path(x).name
            for x in test_module_filenames]

  def FindAllJSModuleFilenames(self):
    return _FindAllJSModuleFilenames(self.source_paths)

  def calc_load_sequence(self):
    return parse_deps.calc_load_sequence(
      self.FindAllJSModuleFilenames(), self)
