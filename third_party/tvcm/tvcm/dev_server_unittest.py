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

  def testTests(self):
    # Just smoke test for a known test to see if things worked.
    resp_str = self.server.Get('/tv/json/tests')
    resp = json.loads(resp_str)
    self.assertTrue('test_module_names' in resp)

  def testTestsWithFilter(self):
    self.server.CallOnServer('SetTestFilterToAllowOnlyFilenamesMatching', 'bbox2_test')
    resp_str = self.server.Get('/tv/json/tests')
    resp = json.loads(resp_str)
    test_module_names = resp['test_module_names']
