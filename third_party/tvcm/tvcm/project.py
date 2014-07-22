# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from tvcm import resource as resource_module
from tvcm import resource_loader
from tvcm import js_module

def _FindAllFilesRecursive(source_paths):
  all_filenames = set()
  for source_path in source_paths:
    for dirpath, dirnames, filenames in os.walk(source_path):
      for f in filenames:
        if f.startswith('.'):
          continue
        x = os.path.abspath(os.path.join(dirpath, f))
        all_filenames.add(x)
  return all_filenames

def _IsFilenameAModule(loader, x):
  if x.endswith(".js"):
    s = loader.GetStrippedJSForFilename(x, early_out_if_no_tvcm=True)
    if not s:
      return
    return js_module.IsJSModule(s, text_is_stripped=True)
  elif x.endswith('.html'):
    return True
  else:
    return False


def _IsFilenameATest(loader, x):
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

class Project(object):
  tvcm_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))

  tvcm_src_path = os.path.abspath(os.path.join(
      tvcm_path, 'src'))

  tvcm_third_party_path = os.path.abspath(os.path.join(
      tvcm_path, 'third_party'))

  def __init__(self, source_paths=None, include_tvcm_paths=True, non_module_html_files=None):
    """
    source_paths: A list of top-level directories in which modules and raw scripts can be found.
        Module paths are relative to these directories.
    """
    self.source_paths = []
    self.non_module_html_files = set()
    if include_tvcm_paths:
      self.source_paths += [
          self.tvcm_src_path,
          os.path.join(self.tvcm_third_party_path, 'Promises', 'polyfill', 'src'),
          os.path.join(self.tvcm_third_party_path, 'gl-matrix', 'src'),
          os.path.join(self.tvcm_third_party_path, 'polymer'),
          os.path.join(self.tvcm_third_party_path, 'd3')
      ]
      local_non_module_html_files = [
        'gl-matrix/jsdoc-template/static/header.html',
        'gl-matrix/jsdoc-template/static/index.html',
        'Promises/polyfill/tests/test.html',
        'Promises/reworked_APIs/IndexedDB/example/after.html',
        'Promises/reworked_APIs/IndexedDB/example/before.html',
        'Promises/reworked_APIs/WebCrypto/example/after.html',
        'Promises/reworked_APIs/WebCrypto/example/before.html'
      ]
      self.non_module_html_files.update(
        [os.path.abspath(os.path.join(self.tvcm_third_party_path, x))
         for x in local_non_module_html_files])

    if source_paths != None:
      self.source_paths += [os.path.abspath(p) for p in source_paths]

    if non_module_html_files != None:
      self.non_module_html_files.update([os.path.abspath(p) for p in non_module_html_files])

    self._loader = None

  @staticmethod
  def FromDict(d):
    return Project(d['source_paths'],
                   include_tvcm_paths=False,
                   non_module_html_files=d.get('non_module_html_files', None))

  def AsDict(self):
    return {
      'source_paths': self.source_paths,
      'non_module_html_files': list(self.non_module_html_files)
    }

  def __repr__(self):
    return "Project(%s)" % repr(self.source_paths)

  def AddSourcePath(self, path):
    self.source_paths.append(path)

  @property
  def loader(self):
    if self._loader == None:
      self._loader = resource_loader.ResourceLoader(self)
    return self._loader

  def ResetLoader(self):
    self._loader = None

  def _FindAllModuleFilenames(self, source_paths):
    all_filenames = _FindAllFilesRecursive(source_paths)
    return [x for x in all_filenames if
            x not in self.non_module_html_files and
            _IsFilenameAModule(self.loader, x)]

  def _FindTestModuleFilenames(self, source_paths):
    all_filenames = _FindAllFilesRecursive(source_paths)
    return [x for x in all_filenames if
            x not in self.non_module_html_files and
            _IsFilenameATest(self.loader, x)]

  def FindAllTestModuleResources(self, start_path=None):
    if start_path == None:
      test_module_filenames = self._FindTestModuleFilenames(self.source_paths)
    else:
      test_module_filenames = self._FindTestModuleFilenames([start_path])
    test_module_filenames.sort()

    # Find the equivalent resources.
    return [self.loader.FindResourceGivenAbsolutePath(x)
            for x in test_module_filenames]

  def FindAllModuleFilenames(self):
    return self._FindAllModuleFilenames(self.source_paths)

  def CalcLoadSequenceForAllModules(self):
    filenames = self.FindAllModuleFilenames()
    return self.CalcLoadSequenceForModuleFilenames(filenames)

  def _Load(self, filenames):
    return [self.loader.LoadModule(module_filename=filename) for
            filename in filenames]

  def CalcLoadSequenceForModuleFilenames(self, filenames):
    modules = self._Load(filenames)
    return self.CalcLoadSequenceForModules(modules)

  def CalcLoadSequenceForModuleNames(self, module_names):
    modules = [self.loader.LoadModule(module_name=name) for
               name in module_names]
    return self.CalcLoadSequenceForModules(modules)

  def CalcLoadSequenceForModules(self, modules):
    already_loaded_set = set()
    load_sequence = []
    for m in modules:
      m.ComputeLoadSequenceRecursive(load_sequence, already_loaded_set)
    return load_sequence
