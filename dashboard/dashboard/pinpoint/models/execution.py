# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class Execution(object):
  """Object tracking the execution of a Quest.

  An Execution object is created for each Quest when it starts running.
  Therefore, each Attempt consists of a list of Executions. The Attempt is
  finished when an Execution fails or when the number of completed Executions is
  equal to the number of Quests. If an Execution fails, the Attempt will have
  fewer Executions in the end.

  Because the Execution is created when the Quest starts running, the lifecycle
  of the Execution object is tied to the work being done. There isn't a state
  where the Execution hasn't started running; it's either running or completed.
  """

  def __init__(self):
    self._blocked = False
    self._completed = False
    self._failed = False
    self._result_values = ()
    self._result_arguments = {}

  @property
  def blocked(self):
    """Returns True iff the Execution is waiting on an external task to finish.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's blocked status.
    """
    return self._blocked

  @property
  def completed(self):
    """Returns True iff the Execution is completed. Otherwise, it's in progress.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's completed status.
    """
    return self._completed

  @property
  def failed(self):
    """Returns True iff the Execution is completed and has failed.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's failed status.
    """
    return self._failed

  @property
  def result_values(self):
    """Data used by auto_explore to determine if two Execution results differ.

    Currently it's just a list of integers or floats. In the future, it will be
    a Catapult Value. For a Build or Test Execution, this is a list containing 0
    or 1 representing success or failure. For a ReadValue Execution, this is a
    list of numbers with the values.
    """
    return self._result_values

  @property
  def result_arguments(self):
    """A dict of information passed on to the next Execution.

    For example, the Build Execution passes the isolated hash to the Test
    Execution.
    """
    return self._result_arguments

  def Poll(self):
    """Update the Execution status."""
    raise NotImplementedError()


class FindIsolated(Execution):

  def __init__(self, configuration, change):
    super(FindIsolated, self).__init__()
    self._configuration = configuration
    self._change = change

  def Poll(self):
    # TODO: Request a build using Buildbucket if needed.
    # TODO: Isolate lookup service.
    self._completed = True
    self._result_values = (0,)
    self._result_arguments = {'isolated_hash': 'this_is_an_isolated_hash'}


class RunTest(Execution):

  def __init__(self, test_suite, test, isolated_hash):
    super(RunTest, self).__init__()
    self._test_suite = test_suite
    self._test = test
    self._isolated_hash = isolated_hash

  def Poll(self):
    # TODO
    self._completed = True
    self._result_values = (0,)


class ReadValue(Execution):

  def __init__(self, metric, file_path):
    super(ReadValue, self).__init__()
    self._metric = metric
    self._file_path = file_path

  def Poll(self):
    # TODO
    self._completed = True
    self._result_values = (0,)
