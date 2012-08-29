#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import os
import subprocess
import sys

root_dir = os.path.join(os.path.dirname(__file__), "..")
src_dir = os.path.join(root_dir, "src")
examples_dir = os.path.join(root_dir, "examples")

FILES_TO_IGNORE = [
  os.path.join(src_dir, "about_tracing.js"),
  os.path.join(src_dir, "deps.js"),
]

def should_lint_file(filename):
  for ignore in FILES_TO_IGNORE:
    if os.path.samefile(filename, ignore):
      return False

  name, ext = os.path.splitext(filename)

  if ext == ".js":
    return True

  if name.endswith("_test") and ext == ".html":
    return True

  return False

def get_all_files_in_dir(start_dir):
  all_filenames = []
  for dirpath, dirnames, filenames in os.walk(start_dir):
    for f in filenames:
      all_filenames.append(os.path.relpath(os.path.join(dirpath, f)))
  return all_filenames

def main(argv):
  all_filenames = []
  all_filenames.extend(get_all_files_in_dir(src_dir))
  all_filenames.extend(get_all_files_in_dir(examples_dir))

  filenames = [f for f in all_filenames if should_lint_file(f)]

  num_errors = 0
  args = ["gjslint", "--strict", "--check_html", "--unix_mode"]
  args.extend(filenames)
  num_errors = subprocess.call(args)

  return num_errors

if __name__ == "__main__":
  sys.exit(main(sys.argv))
