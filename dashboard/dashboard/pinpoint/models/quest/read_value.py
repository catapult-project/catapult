# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.quest import execution
from dashboard.pinpoint.models.quest import quest


class ReadValue(quest.Quest):

  def __init__(self, metric):
    self._metric = metric

  def Start(self, file_path):
    return _ReadValueExecution(self._metric, file_path)


class _ReadValueExecution(execution.Execution):

  def __init__(self, metric, file_path):
    super(_ReadValueExecution, self).__init__()
    self._metric = metric
    self._file_path = file_path

  def _Poll(self):
    # TODO
    self._Complete()
