# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from tvcm import resource as resource_module
from tvcm import resource_loader

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
  if x.endswith('.html'):
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

class AbsFilenameList(object):
  def __init__(self, willDirtyCallback):
    self._willDirtyCallback = willDirtyCallback
    self._filenames = []
    self._filenames_set = set()

  def _WillBecomeDirty(self):
    if self._willDirtyCallback:
      self._willDirtyCallback()

  def append(self, filename):
    assert os.path.isabs(filename)
    self._WillBecomeDirty()
    self._filenames.append(filename)
    self._filenames_set.add(filename)

  def extend(self, iter):
    self._WillBecomeDirty()
    for filename in iter:
      assert os.path.isabs(filename)
      self._filenames.append(filename)
      self._filenames_set.add(filename)

  def appendRel(self, basedir, filename):
    assert os.path.isabs(basedir)
    self._WillBecomeDirty()
    n = os.path.abspath(os.path.join(basedir, filename))
    self._filenames.append(n)
    self._filenames_set.add(n)

  def extendRel(self, basedir, iter):
    self._WillBecomeDirty()
    assert os.path.isabs(basedir)
    for filename in iter:
      n = os.path.abspath(os.path.join(basedir, filename))
      self._filenames.append(n)
      self._filenames_set.add(n)

  def __contains__(self, x):
    return x in self._filenames_set

  def __len__(self):
    return self._filenames.__len__()

  def __iter__(self):
    return iter(self._filenames)

  def __repr__(self):
    return repr(self._filenames)

  def __str__(self):
    return str(self._filenames)


class Project(object):
  tvcm_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))

  tvcm_src_path = os.path.abspath(os.path.join(
      tvcm_path, 'src'))

  def __init__(self, source_paths=None, include_tvcm_paths=True, non_module_html_files=None):
    """
    source_paths: A list of top-level directories in which modules and raw scripts can be found.
        Module paths are relative to these directories.
    """
    self._loader = None
    self._frozen = False
    self.source_paths = AbsFilenameList(self._WillPartOfPathChange)
    self.non_module_html_files = AbsFilenameList(self._WillPartOfPathChange)

    if include_tvcm_paths:
      self.source_paths.append(self.tvcm_src_path)

    if source_paths != None:
      self.source_paths.extend(source_paths)

    if non_module_html_files != None:
      self.non_module_html_files.extend(non_module_html_files)

  def Freeze(self):
    self._frozen = True

  def _WillPartOfPathChange(self):
    if self._frozen:
      raise Exception('The project is frozen. You cannot edit it now')
    self._loader = None

  @staticmethod
  def FromDict(d):
    return Project(d['source_paths'],
                   include_tvcm_paths=False,
                   non_module_html_files=d.get('non_module_html_files', None))

  def AsDict(self):
    return {
      'source_paths': list(self.source_paths),
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
