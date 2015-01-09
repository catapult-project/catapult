# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from trace_viewer import trace_viewer_project

def Main(paths_to_lint):
  project = trace_viewer_project.TraceViewerProject()
  new_paths = [
    os.path.abspath(os.path.join(
      project.trace_viewer_third_party_path, 'python_gflags')),
    os.path.abspath(os.path.join(
      project.trace_viewer_third_party_path, 'closure_linter'))
  ]
  sys.path += new_paths
  try:
    _MainImpl(paths_to_lint)
  finally:
    for p in new_paths:
      sys.path.remove(p)

def _MainImpl(paths_to_lint):
  from closure_linter import gjslint

  if sys.argv[1:] == ['--help']:
    sys.exit(gjslint.main())

  if len(sys.argv) > 1:
    sys.stderr.write('No arguments allowed')
    sys.exit(1)

  sys.argv.append('--strict')
  sys.argv.append('--unix_mode')
  sys.argv.append('--check_html')
  for p in paths_to_lint:
    sys.argv.extend(['-r', os.path.relpath(p)])

  gjslint.main()
