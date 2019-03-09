# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

class PassRetryOnFailureTest(unittest.TestCase):
  _retry = 0

  def test_retry_on_failure(self):
    cls = self.__class__
    if cls._retry == 3:
      return
    cls._retry += 1
    self.fail()

class FailingTest(unittest.TestCase):
  def test_fail(self):
    self.fail()

class AnotherFailingTest(unittest.TestCase):
  def test_fail(self):
    self.fail()

class PassingTest(unittest.TestCase):
  def test_pass(self):
    pass

class SkipTest(unittest.TestCase):
  def test_skip(self):
    self.skipTest('SKIPPING TEST')
