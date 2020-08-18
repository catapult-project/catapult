# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import unittest

from dashboard.pinpoint.models.quest import run_webrtc_test
from dashboard.pinpoint.models.quest import run_test_test

_BASE_ARGUMENTS = {
    'swarming_server': 'server',
    'dimensions': run_test_test.DIMENSIONS,
    'benchmark': 'some_benchmark',
    'builder': 'builder name',
    'target': 'foo_test',
}
_BASE_EXTRA_ARGS = []
_WEBRTCTEST_COMMAND = [
    '../../tools_webrtc/flags_compatibility.py', '../../testing/test_env.py',
    os.path.join('.', 'foo_test')
]
_BASE_SWARMING_TAGS = {}


class FromDictTest(unittest.TestCase):

  def testMinimumArguments(self):
    quest = run_webrtc_test.RunWebRtcTest.FromDict(_BASE_ARGUMENTS)
    expected = run_webrtc_test.RunWebRtcTest('server', run_test_test.DIMENSIONS,
                                             _BASE_EXTRA_ARGS,
                                             _BASE_SWARMING_TAGS,
                                             _WEBRTCTEST_COMMAND,
                                             'out/builder_name')
    self.assertEqual(quest.command, expected.command)
    self.assertEqual(quest.relative_cwd, expected.relative_cwd)
    self.assertEqual(quest, expected)


class StartTest(unittest.TestCase):

  def testStart(self):
    quest = run_webrtc_test.RunWebRtcTest('server', run_test_test.DIMENSIONS,
                                          _BASE_EXTRA_ARGS, _BASE_SWARMING_TAGS,
                                          _WEBRTCTEST_COMMAND,
                                          'out/builder_name')
    execution = quest.Start('change', 'https://isolate.server', 'isolate hash')
    self.assertEqual(execution._execution_timeout_secs, 10800)
