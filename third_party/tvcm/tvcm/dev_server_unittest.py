# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import socket
import httplib
import os
import json

from tvcm import temporary_dev_server

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                           '..', '..', '..', 'src'))
third_party_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                '..', '..', '..', 'third_party'))

class DevServerTests(unittest.TestCase):
  def setUp(self):
    self.server = temporary_dev_server.TemporaryDevServer()

  def tearDown(self):
    self.server.Close()

  def testBasic(self):
    self.server.CallOnServer('AddSourcePathMapping', '/', src_path)
    resp_str = self.server.Get('/base/__init__.js')
    with open(os.path.join(src_path, 'base', '__init__.js'), 'r') as f:
      base_str = f.read()
    self.assertEquals(resp_str, base_str)

  def testDeps(self):
    self.server.CallOnServer('AddSourcePathMapping', '/', src_path)
    self.server.CallOnServer('AddDataPathMapping', '/', third_party_path)

    # Just smoke test that it works.
    resp_str = self.server.Get('/deps.js')

  def testTests(self):
    self.server.CallOnServer('AddSourcePathMapping', '/', src_path)

    # Just smoke test for a known test to see if things worked.
    resp_str = self.server.Get('/json/tests')
    resp = json.loads(resp_str)
    self.assertTrue('base.raf_test' in resp)


if __name__ == '__main__':
  unittest.main()
