# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running a VR Telemetry benchmark in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import posixpath

from dashboard.pinpoint.models.quest import run_telemetry_test


# Benchmarks that need a Daydream View headset paired instead of Cardboard.
DAYDREAM_BENCHMARKS = [
    'xr.browsing.static',
    'xr.browsing.wpr.static',
    'xr.browsing.wpr.smoothness',
]
CARDBOARD_PREFS = posixpath.join(
    'chrome', 'android', 'shared_preference_files', 'test',
    'vr_cardboard_skipdon_setupcomplete.json')
DAYDREAM_PREFS = posixpath.join(
    'chrome', 'android', 'shared_preference_files', 'test',
    'vr_ddview_skipdon_setupcomplete.json')
# We need to apply a profile containing the VR browsing environment asset files
# if the benchmark is a VR browsing benchmark. Currently, this is the same as
# the set of benchmarks that need Daydream View paired.
BROWSING_BENCHMARKS = DAYDREAM_BENCHMARKS
ASSET_PROFILE_PATH = posixpath.join(
    'gen', 'tools', 'perf', 'contrib', 'vr_benchmarks', 'vr_assets_profile')


class RunVrTelemetryTest(run_telemetry_test.RunTelemetryTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = []

    browser = arguments.get('browser')
    if not browser:
      raise TypeError('Missing "browser" argument.')

    if 'android' not in browser:
      raise TypeError('VR tests are currently only supported on Android.')
    if 'bundle' not in browser:
      raise TypeError('VR tests no longer supported on non-bundle builds.')

    extra_test_args.extend(['--install-bundle-module', 'vr'])
    extra_test_args.append('--remove-system-vrcore')

    benchmark = arguments.get('benchmark')
    if not benchmark:
      raise TypeError('Missing "benchmark" argument.')
    extra_test_args.append('--shared-prefs-file')
    if benchmark in DAYDREAM_BENCHMARKS:
      extra_test_args.append(DAYDREAM_PREFS)
    else:
      extra_test_args.append(CARDBOARD_PREFS)

    if benchmark in BROWSING_BENCHMARKS:
      extra_test_args += ('--profile-dir', ASSET_PROFILE_PATH)

    extra_test_args += super(RunVrTelemetryTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
