# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Quest for running an Android instrumentation test in Swarming."""

import copy

from dashboard.pinpoint.models.quest import run_test


_DEFAULT_EXTRA_ARGS = ['--recover-devices']


class RunInstrumentationTest(run_test.RunTest):

  @classmethod
  def _ExtraTestArgs(cls, arguments):
    # TODO(bsheedy): Parse from arguments parameter once we know what will be
    # supported.
    extra_test_args = copy.copy(_DEFAULT_EXTRA_ARGS)
    extra_test_args += super(
        RunInstrumentationTest, cls)._ExtraTestArgs(arguments)
    return extra_test_args
