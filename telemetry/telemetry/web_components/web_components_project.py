# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


from telemetry.core import util
from trace_viewer import trace_viewer_project

def _FindAllFilesRecursive(source_paths, pred):
  all_filenames = set()
  for source_path in source_paths:
    for dirpath, _, filenames in os.walk(source_path):
      for f in filenames:
        if f.startswith('.'):
          continue
        x = os.path.abspath(os.path.join(dirpath, f))
        if pred(x):
          all_filenames.add(x)
  return all_filenames


class WebComponentsProject(trace_viewer_project.TraceViewerProject):
  telemetry_path = os.path.abspath(util.GetTelemetryDir())

  def __init__(self, *args, **kwargs):
    super(WebComponentsProject, self).__init__(*args, **kwargs)

    exclude_paths = [os.path.join(self.telemetry_path, 'docs'),
                     os.path.join(self.telemetry_path, 'unittest_data'),
                     os.path.join(self.telemetry_path, 'support')]
    excluded_html_files = _FindAllFilesRecursive(
        exclude_paths,
        lambda x: x.endswith('.html'))

    self.non_module_html_files.extend(excluded_html_files)
    self.non_module_html_files.appendRel(self.telemetry_path, 'results.html')

    self.source_paths.append(self.telemetry_path)
