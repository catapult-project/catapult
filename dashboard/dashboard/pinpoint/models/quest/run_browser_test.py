# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running a browser test in Swarming."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.pinpoint.models.quest import run_test


_DEFAULT_EXTRA_ARGS = ['--test-launcher-bot-mode']


class RunBrowserTest(run_test.RunTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    extra_test_args = []

    # The browser test launcher only properly parses arguments in the
    # --key=value format.
    test_filter = arguments.get('test-filter')
    if test_filter:
      extra_test_args.append('--gtest_filter=%s' % test_filter)

    extra_test_args += _DEFAULT_EXTRA_ARGS
    extra_test_args += super(RunBrowserTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
