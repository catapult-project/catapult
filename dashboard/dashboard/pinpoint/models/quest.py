# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models import execution


class Quest(object):
  """A description of work to do on a Change.

  Examples include building a binary or running a test. The concept is borrowed
  from Dungeon Master (go/dungeon-master). In Dungeon Master, Quests can depend
  on other Quests, but we're not that fancy here. So instead of having one big
  Quest that depends on smaller Quests, we just run all the small Quests
  linearly. (E.g. build, then test, then read test results). We'd like to
  replace this model with Dungeon Master entirely, when it's ready.

  A Quest has a Start method, which takes as parameters the result_arguments
  from the previous Quest's Execution.
  """

  @property
  def retry_count(self):
    """Returns the number of retries to run if the Quest fails."""
    return 0


class FindIsolated(Quest):

  def __init__(self, configuration):
    self._configuration = configuration

  @property
  def retry_count(self):
    return 1

  def Start(self, change):
    return execution.FindIsolated(self._configuration, change)


class RunTest(Quest):

  def __init__(self, test_suite, test):
    self._test_suite = test_suite
    self._test = test

  @property
  def retry_count(self):
    return 4

  def Start(self, isolated_hash):
    return execution.RunTest(self._test_suite, self._test, isolated_hash)


class ReadValue(Quest):

  def __init__(self, metric):
    self._metric = metric

  def Start(self, file_path):
    return execution.ReadValue(self._metric, file_path)
