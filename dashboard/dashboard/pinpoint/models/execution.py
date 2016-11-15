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

  @property
  def blocked(self):
    """Returns True iff the Execution is waiting on an external task to finish.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's blocked status.
    """
    raise NotImplementedError()

  @property
  def completed(self):
    """Returns True iff the Execution is completed. Otherwise, it's in progress.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's completed status.
    """
    raise NotImplementedError()

  @property
  def failed(self):
    """Returns True iff the Execution is completed and has failed.

    This accessor doesn't contact external servers. Call Poll() to update the
    Execution's failed status.
    """
    raise NotImplementedError()

  @property
  def result_values(self):
    """Data used by auto_explore to determine if two Execution results differ.

    Currently it's just a list of integers or floats. In the future, it will be
    a Catapult Value. For a Build or Test Execution, this is a list containing 0
    or 1 representing success or failure. For a ReadValue Execution, this is a
    list of numbers with the values.
    """
    raise NotImplementedError()

  @property
  def result_arguments(self):
    """A dict of information passed on to the next Execution.

    For example, the Build Execution passes the isolated hash to the Test
    Execution.
    """
    raise NotImplementedError()

  def Poll(self):
    """Update the Execution status."""
    raise NotImplementedError()


class FindIsolated(Execution):

  def __init__(self, change):
    del change
    # TODO: Request a build using Buildbucket if needed.
    # TODO: Isolate lookup service.
    self._task_id = 'foo'

  @property
  def blocked(self):
    return False

  @property
  def completed(self):
    return True

  @property
  def failed(self):
    return False

  @property
  def result_values(self):
    return (0,)

  @property
  def result_arguments(self):
    return {'isolated_hash': 'this_is_an_isolated_hash'}

  def Poll(self):
    pass


class RunTest(Execution):

  def __init__(self, isolated_hash):
    self._isolated_hash = isolated_hash

  @property
  def blocked(self):
    return False

  @property
  def completed(self):
    return True

  @property
  def failed(self):
    return False

  @property
  def result_values(self):
    return (0,)

  @property
  def result_arguments(self):
    return {}

  def Poll(self):
    pass


class ReadValue(Execution):

  @property
  def blocked(self):
    return False

  @property
  def completed(self):
    return True

  @property
  def failed(self):
    return False

  @property
  def result_values(self):
    return (0,)

  @property
  def result_arguments(self):
    return {}

  def Poll(self):
    pass
