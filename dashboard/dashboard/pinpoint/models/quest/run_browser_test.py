# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running a browser test in Swarming."""

import copy

from dashboard.pinpoint.models.quest import run_test


_DEFAULT_EXTRA_ARGS = ['--test-launcher-bot-mode']


class RunBrowserTest(run_test.RunTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    # TODO(bsheedy): Parse from arguments parameter once we know what will be
    # supported.
    extra_test_args = copy.copy(_DEFAULT_EXTRA_ARGS)
    extra_test_args += super(RunBrowserTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
