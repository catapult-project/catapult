# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class ReadValue(quest.Quest):

  def __init__(self, metric):
    self._metric = metric

  def Start(self, isolated_hash):
    return _ReadValueExecution(self._metric, isolated_hash)


class _ReadValueExecution(execution.Execution):

  def __init__(self, metric, isolated_hash):
    super(_ReadValueExecution, self).__init__()
    self._metric = metric
    self._isolated_hash = isolated_hash

  def _Poll(self):
    # TODO
    self._Complete()
