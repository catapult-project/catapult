# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                            '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing import tracing_project


def main():
  project = tracing_project.TracingProject()

  sys.path.append(os.path.join(
      project.tracing_third_party_path, 'python_gflags'))
  sys.path.append(os.path.join(
      project.tracing_third_party_path, 'closure_linter'))

  from closure_linter import fixjsstyle

  os.chdir(project.tracing_src_path)

  fixjsstyle.main()
