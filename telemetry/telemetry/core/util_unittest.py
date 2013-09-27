# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.core import util

class TestWait(unittest.TestCase):
  @staticmethod
  def testNonTimeout():
    def test():
      return True
    util.WaitFor(test, 0.1)

  def testTimeout(self):
    def test():
      return False
    self.assertRaises(util.TimeoutException, lambda: util.WaitFor(test, 0.1))

  def testCallable(self):
    """Test methods and anonymous functions, functions are tested elsewhere."""
    class Test(object):
      def Method(self):
        return 'test'
    util.WaitFor(Test().Method, 0.1)

    util.WaitFor(lambda: 1, 0.1)

    # Test noncallable condition.
    self.assertRaises(TypeError, lambda: util.WaitFor('test', 0.1))

  def testReturn(self):
    self.assertEquals('test', util.WaitFor(lambda: 'test', 0.1))
