# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

top_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(top_dir)

from trace_viewer import trace_viewer_project

from tvcm import parse_html_deps


def Main(args):
  file_name = args[0]
  with open(file_name, 'r') as f:
    contents = f.read()
  res = parse_html_deps.HTMLModuleParser().Parse(contents)
  print res.GenerateJSForHeadlessImport()

if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
