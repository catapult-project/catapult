# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.quest import run_gtest
from dashboard.pinpoint.models.quest import run_test


_MIN_ARGUMENTS = ['--gtest_repeat=1'] + run_test._DEFAULT_EXTRA_ARGS
_ALL_ARGUMENTS = ['--gtest_filter=test_name'] + _MIN_ARGUMENTS


class FromDictTest(unittest.TestCase):

  def testMinimumArguments(self):
    quest = run_gtest.RunGTest.FromDict({'dimensions': {'key': 'value'}})
    expected = run_gtest.RunGTest({'key': 'value'}, _MIN_ARGUMENTS)
    self.assertEqual(quest, expected)

  def testAllArguments(self):
    quest = run_gtest.RunGTest.FromDict({
        'dimensions': {'key': 'value'},
        'test': 'test_name',
    })
    expected = run_gtest.RunGTest({'key': 'value'}, _ALL_ARGUMENTS)
    self.assertEqual(quest, expected)
