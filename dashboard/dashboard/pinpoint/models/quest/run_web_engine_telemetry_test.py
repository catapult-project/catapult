# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Quest for running Lacros perf tests in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import copy

from dashboard.pinpoint.models.quest import run_telemetry_test

_DEFAULT_EXTRA_ARGS = [
    '-d',
    ('--system-image-dir=../../third_party/fuchsia-sdk/'
     'images-internal/astro-release/smart_display_eng_arrested'),
    '--os-check=update',
]


class RunWebEngineTelemetryTest(run_telemetry_test.RunTelemetryTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = super(RunWebEngineTelemetryTest,
                            cls)._ExtraTestArgs(arguments)
    extra_test_args += copy.copy(_DEFAULT_EXTRA_ARGS)
    return extra_test_args

  @classmethod
  def _ComputeCommand(cls, arguments):
    command = [
        'luci-auth',
        'context',
        '--',
        'vpython3',
        '../../testing/scripts/run_performance_tests.py',
        '../../content/test/gpu/run_telemetry_benchmark_fuchsia.py',
    ]
    relative_cwd = arguments.get('relative_cwd', 'out/Release')
    return relative_cwd, command
