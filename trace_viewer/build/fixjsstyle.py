# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from trace_viewer import trace_viewer_project



def main():
  project = trace_viewer_project.TraceViewerProject()

  sys.path.append(os.path.join(
      project.trace_viewer_third_party_path, 'python_gflags'))
  sys.path.append(os.path.join(
      project.trace_viewer_third_party_path, 'closure_linter'))

  from closure_linter import fixjsstyle

  os.chdir(project.src_path)

  fixjsstyle.main()
