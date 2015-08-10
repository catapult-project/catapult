#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

from hooks import install

from tvcm import test_runner

import perf_insights
import perf_insights_build
import perf_insights_examples

def Main(argv):
  parser = argparse.ArgumentParser(
      description='Run python tests.')
  parser.add_argument(
    '--no-install-hooks', dest='install_hooks', action='store_false')
  parser.add_argument('filters', nargs='*')
  parser.set_defaults(install_hooks=True)
  args = parser.parse_args(argv[1:])
  if args.install_hooks:
    install.InstallHooks()

  runner = test_runner.TestRunner()
  runner.AddModule(perf_insights_build)
  runner.AddModule(perf_insights)
  runner.AddModule(perf_insights_examples)
  return runner.Run(args.filters)
