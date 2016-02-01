#!/usr/bin/env python
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

from hooks import install
import lighthouse_project
import vinn


def _RelPathToUnixPath(p):
  return p.replace(os.sep, '/')


def RunTests():
  project = lighthouse_project.LighthouseProject()
  d8_test_module_filenames = ['/' + _RelPathToUnixPath(x)
                              for x in project.FindAllD8TestModuleRelPaths()]
  d8_test_module_filenames.sort()

  cmd = """
  loadHTML('/tracing/base/d8_tests.html');
  """
  res = vinn.RunJsString(
      cmd, source_paths=list(project.source_paths),
      js_args=d8_test_module_filenames, stdout=sys.stdout, stdin=sys.stdin)
  return res.returncode


def Main(argv):
  parser = argparse.ArgumentParser(
      description='Run d8 tests.')
  parser.add_argument(
      '--no-install-hooks', dest='install_hooks', action='store_false')
  parser.set_defaults(install_hooks=True)
  args = parser.parse_args(argv[1:])
  if args.install_hooks:
    install.InstallHooks()

  sys.exit(RunTests())

