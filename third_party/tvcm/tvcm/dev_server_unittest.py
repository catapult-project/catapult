# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import socket
import httplib
import os
import json

from tvcm import project as project_module
from tvcm import temporary_dev_server

class DevServerTests(unittest.TestCase):
  def setUp(self):
    self.server = temporary_dev_server.TemporaryDevServer()

  def tearDown(self):
    self.server.Close()

  def testBasic(self):
    project = project_module.Project()
    resp_str = self.server.Get('/tvcm/__init__.js')
    with open(os.path.join(project.tvcm_src_path, 'tvcm', '__init__.js'), 'r') as f:
      tvcm_str = f.read()
    self.assertEquals(resp_str, tvcm_str)

  def testDeps(self):
    project = project_module.Project()

    # Just smoke test that it works.
    resp_str = self.server.Get('/tvcm/deps.js')

  def testTests(self):
    # Just smoke test for a known test to see if things worked.
    resp_str = self.server.Get('/tvcm/json/tests')
    resp = json.loads(resp_str)
    self.assertTrue('test_module_names' in resp)
    self.assertTrue('tvcm.raf_test' in resp['test_module_names'])


if __name__ == '__main__':
  unittest.main()
