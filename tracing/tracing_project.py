# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os
import re


def _AddToPathIfNeeded(path):
  if path not in sys.path:
    sys.path.insert(0, path)


def UpdateSysPathIfNeeded():
  p = TracingProject()
  _AddToPathIfNeeded(p.catapult_path)
  _AddToPathIfNeeded(p.tvcm_path)
  _AddToPathIfNeeded(p.vinn_path)

  _AddToPathIfNeeded(os.path.join(p.catapult_third_party_path, 'WebOb'))
  _AddToPathIfNeeded(os.path.join(p.catapult_third_party_path, 'Paste'))
  _AddToPathIfNeeded(os.path.join(p.catapult_third_party_path, 'six'))
  _AddToPathIfNeeded(os.path.join(p.catapult_third_party_path, 'webapp2'))


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


class TracingProject():
  catapult_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
  tracing_root_path = os.path.abspath(os.path.join(catapult_path, 'tracing'))
  tracing_src_path = os.path.abspath(os.path.join(tracing_root_path, 'tracing'))
  extras_path = os.path.join(tracing_src_path, 'extras')
  ui_extras_path = os.path.join(tracing_src_path, 'ui', 'extras')


  catapult_third_party_path = os.path.abspath(os.path.join(
      catapult_path, 'third_party'))

  tracing_third_party_path = os.path.abspath(os.path.join(
      tracing_root_path, 'third_party'))
  tvcm_path = os.path.abspath(os.path.join(tracing_third_party_path, 'tvcm'))
  vinn_path = os.path.abspath(os.path.join(catapult_third_party_path, 'vinn'))

  jszip_path = os.path.abspath(os.path.join(tracing_third_party_path, 'jszip'))

  glmatrix_path = os.path.abspath(os.path.join(
      tracing_third_party_path, 'gl-matrix', 'dist'))

  ui_path = os.path.abspath(os.path.join(tracing_src_path, 'ui'))
  d3_path = os.path.abspath(os.path.join(tracing_third_party_path, 'd3'))
  chai_path = os.path.abspath(os.path.join(tracing_third_party_path, 'chai'))
  mocha_path = os.path.abspath(os.path.join(tracing_third_party_path, 'mocha'))

  test_data_path = os.path.join(tracing_root_path, 'test_data')
  skp_data_path = os.path.join(tracing_root_path, 'skp_data')

  rjsmin_path = os.path.abspath(os.path.join(
      tracing_third_party_path, 'tvcm', 'third_party', 'rjsmin'))
  rcssmin_path = os.path.abspath(os.path.join(
      tracing_third_party_path, 'tvcm', 'third_party', 'rcssmin'))

  def __init__(self):
    self.source_paths = []
    self.source_paths.append(self.tracing_root_path)
    self.source_paths.append(self.tracing_third_party_path)
    self.source_paths.append(self.jszip_path)
    self.source_paths.append(self.glmatrix_path)
    self.source_paths.append(self.d3_path)
    self.source_paths.append(self.chai_path)
    self.source_paths.append(self.mocha_path)

  def CreateVulcanizer(self):
    from tvcm import project as project_module
    return project_module.Project(self.source_paths)

  def IsD8CompatibleFile(self, filename):
    return not filename.startswith(self.ui_path)

  def FindAllTestModuleRelPaths(self, pred=None):
    if pred is None:
      pred = lambda x: True

    all_filenames = _FindAllFilesRecursive([self.tracing_src_path])
    test_module_filenames = [x for x in all_filenames if
                             _IsFilenameATest(x) and pred(x)]
    test_module_filenames.sort()

    return [os.path.relpath(x, self.tracing_root_path)
            for x in test_module_filenames]

  def FindAllD8TestModuleRelPaths(self):
    return self.FindAllTestModuleRelPaths(pred=self.IsD8CompatibleFile)

  def GetConfigNames(self):
    config_files = [
        os.path.join(self.ui_extras_path, x)
        for x in os.listdir(self.ui_extras_path)
        if x.endswith('_config.html')
    ]

    config_files = [x for x in config_files if os.path.isfile(x)]

    config_basenames = [os.path.basename(x) for x in config_files]
    config_names = [re.match('(.+)_config.html$', x).group(1)
                    for x in config_basenames]
    return config_names

  def GetDefaultConfigName(self):
    assert 'full' in self.GetConfigNames()
    return 'full'

  def AddConfigNameOptionToParser(self, parser):
    choices = self.GetConfigNames()
    parser.add_argument(
        '--config', dest='config_name',
        choices=choices, default=self.GetDefaultConfigName(),
        help='Picks a browser config. Valid choices: %s' % ', '.join(choices))
    return choices

  def GetModuleNameForConfigName(self, config_name):
    return 'tracing.ui.extras.%s_config' % config_name

