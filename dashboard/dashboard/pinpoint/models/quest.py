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
  """

  @property
  def execution_class(self):
    raise NotImplementedError()

  @property
  def retry_count(self):
    """Returns the number of retries to run if the Quest fails."""
    return 0

  def Start(self, *args, **kwargs):
    """Start an execution of the Quest.

    Quests use an asynchronous model, because they often call out to other task
    distributors.

    Args:
      args: The result_arguments from the previous Quest's Execution.

    Returns:
      An Execution object corresponding to this Quest.
    """
    return self.execution_class(*args, **kwargs)


class FindIsolated(Quest):

  def __init__(self, configuration):
    self._configuration = configuration

  @property
  def execution_class(self):
    return execution.FindIsolated

  @property
  def retry_count(self):
    return 1


class RunTest(Quest):

  def __init__(self, test_suite, test):
    self._test_suite = test_suite
    self._test = test

  @property
  def execution_class(self):
    return execution.RunTest

  @property
  def retry_count(self):
    return 4


class ReadValue(Quest):

  def __init__(self, metric):
    self._metric = metric

  @property
  def execution_class(self):
    return execution.ReadValue
