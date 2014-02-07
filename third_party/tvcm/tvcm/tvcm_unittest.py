# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import sys
import os

from tvcm import module_test_case

tvcm_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..'))
third_party_path = os.path.abspath(os.path.join(
    tvcm_path, '..'))

base_path = os.path.abspath(os.path.join(
  tvcm_path, 'base'))
ui_path = os.path.abspath(os.path.join(
  tvcm_path, 'ui'))

def load_tests(loader, tests, pattern):
  suite = unittest.TestSuite()
  suite.addTest(module_test_case.DiscoverTestsInModule(
      [tvcm_path], [third_party_path],
      tvcm_path))
  return suite
