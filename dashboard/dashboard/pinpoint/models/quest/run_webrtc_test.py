# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Quest for running WebRTC perf tests in Swarming."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
from dashboard.pinpoint.models.quest import run_test


def _StoryToGtestName(story_name):
  gtest_name = '_'.join(word.title() for word in story_name.split('_'))
  if story_name.endswith('_alice'):
    gtest_name = gtest_name[:-len('_alice')]
  elif story_name.endswith('_bob'):
    gtest_name = gtest_name[:-len('_bob')]
  return gtest_name


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

  def Start(self, change, isolate_server, isolate_hash):
    return self._Start(
        change,
        isolate_server,
        isolate_hash,
        self._extra_args,
        swarming_tags={},
        execution_timeout_secs=10800)

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    results_filename = '${ISOLATED_OUTDIR}/webrtc_perf_tests/perf_results.json'
    extra_test_args = [
        '--test_artifacts_dir=${ISOLATED_OUTDIR}',
        '--nologs',
        '--isolated-script-test-perf-output=%s' % results_filename,
    ]
    # Gtests are filtered based on the story name.
    story = arguments.get('story')
    if story:
      extra_test_args.append('--gtest_filter=*.%s' % _StoryToGtestName(story))

    extra_test_args += super(RunWebRtcTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args


def _SanitizeFileName(name):
  safe_with_spaces = ''.join(c if c.isalnum() else ' ' for c in name)
  return '_'.join(safe_with_spaces.split())
