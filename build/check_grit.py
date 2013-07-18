# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import parse_deps
import re

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))

def GritCheck():
  filenames = [os.path.join(srcdir, x) for x in [
      "base.js",
      "about_tracing/profiling_view.js"]]

  grit_files = []
  load_sequence = parse_deps.calc_load_sequence(filenames, srcdir)
  for module in load_sequence:
    for style_sheet in module.style_sheets:
      # I'm assuming we only have url()'s associated with images
      grit_files.extend(re.findall(
          'url\((?:["|\']?)([^"\'()]*)(?:["|\']?)\)',
          style_sheet.contents))

  for idx, filename in enumerate(grit_files):
    while filename.startswith("../"):
      filename = filename[3:]
    grit_files[idx] = "src/" + filename

  known_images = []
  for (dirpath, dirnames, filenames) in os.walk('src/images'):
    for name in filenames:
      known_images.append(os.path.join(dirpath, name))

  u = set(grit_files).union(set(known_images))
  i = set(grit_files).intersection(set(known_images))
  diff = list(u - i)

  if len(diff) == 0:
    return ''

  error = 'Entries in CSS url()s do not match files in src/images:\n'
  in_grit_only = list(set(grit_files) - set(known_images))
  in_known_only = list(set(known_images) - set(grit_files))

  if len(in_grit_only) > 0:
    error += ' In CSS urls()s only:\n   ' + '\n   '.join(sorted(in_grit_only))
  if len(in_known_only) > 0:
    if len(in_grit_only) > 0:
      error += '\n\n'
    error += ' In src/images only:\n   ' + '\n   '.join(sorted(in_known_only))

  return error
