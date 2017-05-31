# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class ReadValue(quest.Quest):

  def __init__(self, metric):
    self._metric = metric

  def __str__(self):
    return 'Value of ' + self._metric

  def Start(self, isolate_hash):
    return _ReadValueExecution(self._metric, isolate_hash)


class _ReadValueExecution(execution.Execution):

  def __init__(self, metric, isolate_hash):
    super(_ReadValueExecution, self).__init__()
    self._metric = metric
    self._isolate_hash = isolate_hash

  def _Poll(self):
    # TODO
    self._Complete()
