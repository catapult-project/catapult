# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys
import os


from tvcm import project as project_module


class TraceViewerProject(project_module.Project):
  trace_viewer_path = os.path.abspath(os.path.join(
      os.path.dirname(__file__), '..'))

  src_path = os.path.abspath(os.path.join(
      trace_viewer_path, 'trace_viewer'))

  trace_viewer_third_party_path = os.path.abspath(os.path.join(
      trace_viewer_path, 'third_party'))

  jszip_path = os.path.abspath(os.path.join(
      trace_viewer_third_party_path, 'jszip'))

  test_data_path = os.path.join(trace_viewer_path, 'test_data')
  skp_data_path = os.path.join(trace_viewer_path, 'skp_data')

  def __init__(self, other_paths=None):
    paths = [self.src_path, self.jszip_path]
    if other_paths:
      paths.extend(other_paths)
    super(TraceViewerProject, self).__init__(
      paths)

    non_module_html_files = [
      'test_data/android_systrace.html',
      'third_party/jszip/examples/download-zip-file.html',
      'third_party/jszip/examples/get-binary-files-xhr2.html',
      'third_party/jszip/examples/read-local-file-api.html',
      'third_party/jszip/index.html',
      'third_party/jszip/test/index.html'
    ]
    self.non_module_html_files.update(
      [os.path.abspath(os.path.join(self.trace_viewer_path, x))
       for x in non_module_html_files])
