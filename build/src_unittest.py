# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from tvcm import module_test_case

toplevel_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'))
tvcm_path = os.path.join(toplevel_path, 'third_party', 'tvcm')
src_path = os.path.join(toplevel_path, 'src')
third_party_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                "../third_party"))

def load_tests(loader, tests, pattern):
  return module_test_case.DiscoverTestsInModule(
      [tvcm_path, src_path], [third_party_path],
      src_path)
