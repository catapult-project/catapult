# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import socket
import httplib
import os
import json

from tvcm import temporary_dev_server

TVCM_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
THIRD_PARTY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..', '..'))

class DevServerTests(unittest.TestCase):
  def setUp(self):
    self.server = temporary_dev_server.TemporaryDevServer()

  def tearDown(self):
    self.server.Close()

  def testBasic(self):
    self.server.CallOnServer('AddSourcePathMapping', TVCM_PATH)
    resp_str = self.server.Get('/base/__init__.js')
    with open(os.path.join(TVCM_PATH, 'base', '__init__.js'), 'r') as f:
      base_str = f.read()
    self.assertEquals(resp_str, base_str)

  def testDeps(self):
    self.server.CallOnServer('AddSourcePathMapping', TVCM_PATH)
    self.server.CallOnServer('AddDataPathMapping', THIRD_PARTY_PATH)

    # Just smoke test that it works.
    resp_str = self.server.Get('/base/deps.js')

  def testTests(self):
    self.server.CallOnServer('AddSourcePathMapping', TVCM_PATH)

    # Just smoke test for a known test to see if things worked.
    resp_str = self.server.Get('/base/json/tests')
    resp = json.loads(resp_str)
    self.assertTrue('base.raf_test' in resp)


if __name__ == '__main__':
  unittest.main()
