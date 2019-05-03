# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running a GTest in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.pinpoint.models.quest import run_performance_test


_DEFAULT_EXTRA_ARGS = ['--non-telemetry', 'true']


class RunGTest(run_performance_test.RunPerformanceTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = []

    test = arguments.get('test')
    if test:
      extra_test_args.append('--gtest_filter=' + test)

    extra_test_args.append('--gtest_repeat=1')
    extra_test_args.append('--gtest-benchmark-name')
    extra_test_args.append(arguments.get('benchmark'))

    extra_test_args += _DEFAULT_EXTRA_ARGS
    extra_test_args += super(RunGTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
