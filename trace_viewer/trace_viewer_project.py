# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys
import os
import re


from tvcm import project as project_module


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


class TraceViewerProject(project_module.Project):
  trace_viewer_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))

  src_path = os.path.abspath(os.path.join(
      trace_viewer_path, 'trace_viewer'))

  extras_path = os.path.join(src_path, 'extras')

  trace_viewer_third_party_path = os.path.abspath(os.path.join(
      trace_viewer_path, 'third_party'))

  jszip_path = os.path.abspath(os.path.join(
      trace_viewer_third_party_path, 'jszip'))

  glmatrix_path = os.path.abspath(os.path.join(
      trace_viewer_third_party_path, 'gl-matrix', 'dist'))

  d3_path = os.path.abspath(os.path.join(
      trace_viewer_third_party_path, 'd3'))

  test_data_path = os.path.join(trace_viewer_path, 'test_data')
  skp_data_path = os.path.join(trace_viewer_path, 'skp_data')

  def __init__(self, *args, **kwargs):
    super(TraceViewerProject, self).__init__(*args, **kwargs)

    self.source_paths.append(self.src_path)
    self.source_paths.append(self.trace_viewer_third_party_path)
    self.source_paths.append(self.jszip_path)
    self.source_paths.append(self.glmatrix_path)
    self.source_paths.append(self.d3_path)

    self.non_module_html_files.extendRel(self.trace_viewer_path, [
      'bin/index.html',
      'test_data/android_systrace.html',
    ])
    for config_name in self.GetConfigNames():
      self.non_module_html_files.appendRel(self.trace_viewer_path,
        'bin/trace_viewer_%s.html' % config_name)

    # Igore the old viewer if it still exists.
    self.non_module_html_files.appendRel(self.trace_viewer_path,
      'bin/trace_viewer.html')

    self.non_module_html_files.extendRel(self.trace_viewer_third_party_path, [
      'gl-matrix/jsdoc-template/static/header.html',
      'gl-matrix/jsdoc-template/static/index.html',
    ])

  def GetConfigNames(self):
    config_files = [
        os.path.join(self.extras_path, x) for x in os.listdir(self.extras_path)
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
    parser.add_option(
        '--config', dest='config_name',
        type='choice', choices=choices,
        default=self.GetDefaultConfigName(),
        help='Picks a browser config. Valid choices: %s' % ', '.join(choices))
    return choices

  def GetModuleNameForConfigName(self, config_name):
    return 'extras.%s_config' % config_name