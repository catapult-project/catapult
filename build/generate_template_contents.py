#!/usr/bin/env python
# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import parse_deps
import os

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))

def generate_templates():
  all_filenames = []

  for dirpath, dirnames, filenames in os.walk(srcdir):
    for f in filenames:
      all_filenames.append(os.path.join(dirpath, f))

  filenames = [x for x in all_filenames if
               os.path.splitext(x)[1] == ".html"]
  filenames = [os.path.relpath(x) for x in filenames]

  def ignored(x):
    if os.path.basename(x).startswith('.'):
      return True
    if "tests.html" in x:
      return True
    if "about_tracing.html" in x:
      return True
    return False
  filenames = [x for x in filenames if not ignored(x)]

  templates = '';

  for filename in filenames:
    f = open(filename, 'r')
    templates += f.read()
    f.close()

  return templates
