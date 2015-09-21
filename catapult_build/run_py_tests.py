#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys
import unittest

from hooks import install


def RunTests(base_dir, pattern='*_unittest.py'):
  """Runs Python unit tests found in the given directory."""
  # TODO(qyearsley): Use args.filters (in the same way tvcm.test_runner does).
  parser = argparse.ArgumentParser(description='Run python tests.')
  parser.add_argument(
      '--no-install-hooks', dest='install_hooks', action='store_false')
  parser.add_argument('filters', nargs='*')
  parser.set_defaults(install_hooks=True)
  args = parser.parse_args()

  if args.install_hooks:
    install.InstallHooks()

  tests = unittest.TestLoader().discover(base_dir, pattern=pattern)
  result = unittest.TextTestRunner(verbosity=2).run(tests)
  return 0 if result.wasSuccessful() else 1
