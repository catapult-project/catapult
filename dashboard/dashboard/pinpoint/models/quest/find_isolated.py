# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models import execution
from dashboard.pinpoint.models.quest import quest


class FindIsolated(quest.Quest):

  def __init__(self, configuration):
    self._configuration = configuration

  @property
  def retry_count(self):
    return 1

  def Start(self, change):
    return _FindIsolatedExecution(self._configuration, change)


class _FindIsolatedExecution(execution.Execution):

  def __init__(self, configuration, change):
    super(_FindIsolatedExecution, self).__init__()
    self._configuration = configuration
    self._change = change

  def Poll(self):
    # TODO: Request a build using Buildbucket if needed.
    # TODO: Isolate lookup service.
    self._completed = True
    self._result_values = (0,)
    self._result_arguments = {'isolated_hash': 'this_is_an_isolated_hash'}
