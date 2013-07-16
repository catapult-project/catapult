# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

GYP_FILE = "trace_viewer.gyp"
FILE_GROUPS = ["tracing_html_files",
    "tracing_css_files",
    "tracing_js_files",
    "tracing_template_files",
    "tracing_img_files"]

def GypCheck():
  f = open(GYP_FILE, 'r')
  gyp = f.read()
  f.close()

  data = eval(gyp)
  gyp_files = []
  for group in FILE_GROUPS:
    gyp_files.extend(data["variables"][group])

  known_files = []
  for (dirpath, dirnames, filenames) in os.walk('src'):
    for name in filenames:
      if not name.endswith(("_test.js", "_test_data.js", "tests.html")):
        known_files.append(os.path.join(dirpath, name))

  u = set(gyp_files).union(set(known_files))
  i = set(gyp_files).intersection(set(known_files))
  diff = list(u - i)

  if len(diff) == 0:
    return ''

  error = 'Entries in ' + GYP_FILE + ' do not match files on disk:\n'
  in_gyp_only = list(set(gyp_files) - set(known_files))
  in_known_only = list(set(known_files) - set(gyp_files))

  if len(in_gyp_only) > 0:
    error += '  In GYP only:\n    ' + '\n    '.join(sorted(in_gyp_only))
  if len(in_known_only) > 0:
    if len(in_gyp_only) > 0:
      error += '\n\n'
    error += '  On disk only:\n    ' + '\n    '.join(sorted(in_known_only))

  return error
