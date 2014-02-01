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


class SrcModulesTest(module_test_case.ModuleTestCase):
  def __init__(self, method_name):
    super(SrcModulesTest, self).__init__(
        [tvcm_path, src_path], [third_party_path],
        method_name=method_name)

def load_tests(loader, tests, pattern):
  suite = unittest.TestSuite()
  t = SrcModulesTest('runTest')
  suite.addTest(t)
  return suite
