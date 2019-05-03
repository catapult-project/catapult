# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import unittest

from dashboard.pinpoint.models.quest import run_performance_test
from dashboard.pinpoint.models.quest import run_telemetry_test
from dashboard.pinpoint.models.quest import run_vr_telemetry_test
from dashboard.pinpoint.models.quest import run_test_test

_BASE_ARGUMENTS = {
    'swarming_server': 'server',
    'dimensions': run_test_test.DIMENSIONS,
    'browser': 'android-chromium',
}
_BROWSING_ARGUMENTS = _BASE_ARGUMENTS.copy()
_BROWSING_ARGUMENTS['benchmark'] = 'xr.browsing.static'
_CARDBOARD_ARGUMENTS = _BASE_ARGUMENTS.copy()
_CARDBOARD_ARGUMENTS['benchmark'] = 'xr.webxr.static'

_COMBINED_DEFAULT_EXTRA_ARGS = (run_telemetry_test._DEFAULT_EXTRA_ARGS
                                + run_performance_test._DEFAULT_EXTRA_ARGS)

_BASE_EXTRA_ARGS = [
    '--pageset-repeat', '1',
    '--browser', 'android-chromium',
] + _COMBINED_DEFAULT_EXTRA_ARGS
_BROWSING_EXTRA_ARGS = [
    '--shared-prefs-file', run_vr_telemetry_test.DAYDREAM_PREFS,
    '--profile-dir', run_vr_telemetry_test.ASSET_PROFILE_PATH,
    '--benchmarks', 'xr.browsing.static'] + _BASE_EXTRA_ARGS
_CARDBOARD_EXTRA_ARGS = [
    '--shared-prefs-file', run_vr_telemetry_test.CARDBOARD_PREFS,
    '--benchmarks', 'xr.webxr.static'] + _BASE_EXTRA_ARGS


_BASE_SWARMING_TAGS = {}


class FromDictTest(unittest.TestCase):

  def testMinimumArgs(self):
    with self.assertRaises(TypeError):
      run_vr_telemetry_test.RunVrTelemetryTest.FromDict(_BASE_ARGUMENTS)

  def testNonAndroid(self):
    with self.assertRaises(TypeError):
      arguments = dict(_CARDBOARD_ARGUMENTS)
      arguments['browser'] = 'release'
      run_vr_telemetry_test.RunVrTelemetryTest.FromDict(arguments)

  def testCardboardArgs(self):
    quest = run_vr_telemetry_test.RunVrTelemetryTest.FromDict(
        _CARDBOARD_ARGUMENTS)
    expected = run_vr_telemetry_test.RunVrTelemetryTest(
        'server', run_test_test.DIMENSIONS, _CARDBOARD_EXTRA_ARGS,
        _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)

  def testBrowsingArgs(self):
    quest = run_vr_telemetry_test.RunVrTelemetryTest.FromDict(
        _BROWSING_ARGUMENTS)
    expected = run_vr_telemetry_test.RunVrTelemetryTest(
        'server', run_test_test.DIMENSIONS, _BROWSING_EXTRA_ARGS,
        _BASE_SWARMING_TAGS)
    self.assertEqual(quest, expected)
