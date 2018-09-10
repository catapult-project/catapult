# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models.quest import run_instrumentation_test

_BASE_ARGUMENTS = {
    'swarming_server': 'server',
    'dimensions': {'key': 'value'},
}


_BASE_EXTRA_ARGS = run_instrumentation_test._DEFAULT_EXTRA_ARGS


class FromDictTest(unittest.TestCase):

  def testMinimumArguments(self):
    quest = run_instrumentation_test.RunInstrumentationTest.FromDict(
        _BASE_ARGUMENTS)
    expected = run_instrumentation_test.RunInstrumentationTest(
        'server', {'key': 'value'}, _BASE_EXTRA_ARGS)
    self.assertEqual(quest, expected)
