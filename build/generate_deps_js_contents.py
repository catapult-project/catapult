#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import parse_deps
import os

srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))

def generate_deps_js():
  all_filenames = []

  for dirpath, dirnames, filenames in os.walk(srcdir):
    for f in filenames:
      all_filenames.append(os.path.join(dirpath, f))

  filenames = [x for x in all_filenames if
               os.path.splitext(x)[1] == ".js"]
  filenames = [os.path.relpath(x) for x in filenames]

  def ignored(x):
    if os.path.basename(x).startswith('.'):
      return True
    return False
  filenames = [x for x in filenames if not ignored(x)]

  load_sequence = parse_deps.calc_load_sequence(filenames, srcdir)

  chunks = []
  for module in load_sequence:
    for dependent_module_name in module.dependent_module_names:
      chunks.append("base.addModuleDependency('%s','%s');\n" % (
          module.name, dependent_module_name));

    for dependent_raw_script_name in module.dependent_raw_script_names:
      chunks.append(
          "base.addModuleRawScriptDependency('%s','%s');\n" % (
          module.name, dependent_raw_script_name));

    for style_sheet in module.style_sheets:
      chunks.append("base.addModuleStylesheet('%s','%s');\n" % (
          module.name, style_sheet.name));
  return "".join(chunks)

