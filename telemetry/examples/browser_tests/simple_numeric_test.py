# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import string
import time

from telemetry.testing import serially_executed_browser_test_case


class SimpleTest(serially_executed_browser_test_case.SeriallyBrowserTestCase):

  @classmethod
  def AddCommandlineArgs(cls, parser):
    parser.add_option('--adder-sum', type=int, default=5)

  def setUp(self):
    self.extra = 5

  @classmethod
  def GenerateTestCases_AdderTest(cls, options):
    yield 'add_1_and_2', (1, 2, options.adder_sum)
    yield 'add_2_and_3', (2, 3, options.adder_sum)
    yield 'add_7_and_3', (7, 3, options.adder_sum)
    # Filtered out in browser_test_runner_unittest.py
    yield 'dontrun_add_1_and_2', (1, 2, options.adder_sum)

  @classmethod
  def GenerateTestCases_AlphabeticalTest(cls, options):
    del options  # unused
    prefix = 'Alphabetical_'
    for character in string.lowercase[:26]:
      yield prefix + character, ()
    for character in string.uppercase[:26]:
      yield prefix + character, ()
    for num in xrange(20):
      yield prefix + str(num), ()

  def AlphabeticalTest(self):
    pass

  def AdderTest(self, a, b, partial_sum):
    self.assertEqual(a + b, partial_sum)

  @classmethod
  def GenerateTestCases_MultiplierTest(cls, options):
    del options  # unused
    yield 'multiplier_simple', (10, 2, 4)
    yield 'multiplier_simple_2', (2, 3, 5)
    yield 'multiplier_simple_3', (10, 3, 6)
    # Filtered out in browser_test_runner_unittest.py
    yield 'dontrun_multiplier_simple', (10, 2, 4)

  def MultiplierTest(self, a, b, partial_sum):
    self.assertEqual(a * b, partial_sum * self.extra)

  def TestSimple(self):
    time.sleep(0.5)
    self.assertEqual(1, self.extra)
