# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from telemetry.testing import serially_executed_browser_test_case


class SimpleTest(serially_executed_browser_test_case.SeriallyBrowserTestCase):

  @classmethod
  def AddCommandlineArgs(cls, parser):
    parser.add_option('--adder-sum', type=int, default=5)

  def setUp(self):
    self.extra = 5
    self.start_time = time.time()

  def tearDown(self):
    t = (time.time() - self.start_time) * 1000
    print '%s: %.3fms' % (self.id(), t)

  @classmethod
  def GenerateTestCases_TestFoo(cls, options):
    yield 'add_1_and_2', (1, 2, options.adder_sum)
    yield 'add_2_and_3', (2, 3, options.adder_sum)
    yield 'add_7_and_3', (7, 3, options.adder_sum)

  def TestFoo(self, a, b, partial_sum):
    self.assertEqual(a + b, partial_sum)

  @classmethod
  def GenerateTestCases_TestBar(cls, options):
    del options  # unused
    yield 'multiplier_simple', (10, 2, 4)
    yield 'multiplier_simple_2', (2, 3, 5)
    yield 'multiplier_simple_3', (10, 3, 6)

  def TestBar(self, a, b, partial_sum):
    self.assertEqual(a * b, partial_sum * self.extra)

  def testSimple(self):
    time.sleep(2)
    self.assertEqual(1, self.extra)
