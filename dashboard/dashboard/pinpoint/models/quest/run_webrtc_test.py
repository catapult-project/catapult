# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Quest for running WebRTC perf tests in Swarming."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
from dashboard.pinpoint.models.quest import run_test


class RunWebRtcTest(run_test.RunTest):

  @classmethod
  def _ComputeCommand(cls, arguments):
    if 'target' not in arguments:
      raise ValueError('Missing "target" in arguments.')

    # This is the command used to run webrtc_perf_tests.
    command = arguments.get('command', [
        '../../tools_webrtc/flags_compatibility.py',
        '../../testing/test_env.py',
        os.path.join('.', arguments.get('target'))
    ])
    # The tests are run in the builder out directory.
    builder_cwd = _SanitizeFileName(arguments.get('builder'))
    relative_cwd = arguments.get('relative_cwd', 'out/' + builder_cwd)
    return relative_cwd, command


def _SanitizeFileName(name):
  safe_with_spaces = ''.join(c if c.isalnum() else ' ' for c in name)
  return '_'.join(safe_with_spaces.split())
