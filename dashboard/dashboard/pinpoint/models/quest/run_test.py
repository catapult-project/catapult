# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class RunTest(quest.Quest):

  def __init__(self, test_suite, test):
    self._test_suite = test_suite
    self._test = test

  @property
  def retry_count(self):
    return 4

  def Start(self, isolated_hash):
    return _RunTestExecution(self._test_suite, self._test, isolated_hash)


class _RunTestExecution(execution.Execution):

  def __init__(self, test_suite, test, isolated_hash):
    super(_RunTestExecution, self).__init__()
    self._test_suite = test_suite
    self._test = test
    self._isolated_hash = isolated_hash

  def _Poll(self):
    # TODO
    self._Complete()
