# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Quest for running Fuchsia perf tests in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import copy
import json

from dashboard.pinpoint.models.quest import run_telemetry_test
import six

_DEFAULT_EXTRA_ARGS = [
    '-d',
    '--os-check=check',
]
DEFAULT_IMAGE_PATH = ('--system-image-dir=../../third_party/fuchsia-sdk'
                      '/images-internal/%s/%s')
IMAGE_MAP = {
    'astro': ('astro-release', 'smart_display_eng_arrested'),
    'sherlock': ('sherlock-release', 'smart_display_max_eng_arrested'),
    'atlas': ('chromebook-x64-release', 'sucrose_eng'),
}


class RunWebEngineTelemetryTest(run_telemetry_test.RunTelemetryTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = super(RunWebEngineTelemetryTest,
                            cls)._ExtraTestArgs(arguments)
    image_path = (None, None)
    dimensions = arguments.get('dimensions')
    if isinstance(dimensions, six.string_types):
      dimensions = json.loads(dimensions)
    for key_value in dimensions:
      if key_value['key'] == 'device_type':
        image_path = IMAGE_MAP[key_value['value'].lower()]
        break
    extra_test_args += copy.copy(_DEFAULT_EXTRA_ARGS)
    if all(image_path) and len(image_path) == 2:
      extra_test_args.append(DEFAULT_IMAGE_PATH % image_path)
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
