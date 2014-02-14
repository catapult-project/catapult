# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import os
import re

from tvcm import presubmit_checker
from tvcm import fake_fs

class FakeInputAPIChange(object):
  def __init__(self, input_api):
    self.input_api = input_api

  def AffectedFiles(file_filter, include_deletes):
    return [x for x in self.input_api.affected_files if
            file_filter(f)]

class FakeInputAPI(object):
  def __init__(self):
    self.re = re
    self.os_path = os.path
    self.change = FakeInputAPIChange(self)
    self.affected_files = []

class FakeOutputAPI(object):
  def PresubmitError(self, msg):
    return msg

  def PresubmitNotifyResult(self, msg):
    return msg

class PresubmitCheckerTest(unittest.TestCase):
  def testSmoke(self):
    input_api = FakeInputAPI()
    output_api = FakeOutputAPI()

    fs = fake_fs.FakeFS()
    fs.AddFile('/x/y.js', """
'use strict';
function test() {
  return 3;
}
""")
    fs.AddFile('/x/y.css', """
.foo {
    a: b;
    b: c;
}
""")
    input_api.affected_files += ['/x/y.js', '/x/y.css']
    with fs:
      checker = presubmit_checker.PresubmitChecker(input_api, output_api)
      checker.RunChecks()
