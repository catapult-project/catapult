# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import traceback


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
    self._completed = False
    self._failed = False
    self._result_values = ()
    self._result_arguments = {}

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
    assert self.completed
    return self._result_values

  @property
  def result_arguments(self):
    """A dict of information passed on to the next Execution.

    For example, the Build Execution passes the isolate hash to the Test
    Execution.
    """
    assert self.completed
    return self._result_arguments

  def Poll(self):
    """Update the Execution status."""
    assert not self.completed

    try:
      self._Poll()
    except StandardError:
      # StandardError most likely indicates a bug in the code.
      # We should fail fast to aid debugging.
      raise
    except Exception:  # pylint: disable=broad-except
      # We allow broad exception handling here, because we log the exception and
      # display it in the UI.
      self._completed = True
      self._failed = True
      self._result_values = (traceback.format_exc(),)


  def _Poll(self):
    raise NotImplementedError()

  def _Complete(self, result_values=None, result_arguments=None):
    self._completed = True
    self._failed = False
    self._result_values = result_values or (None,)
    self._result_arguments = result_arguments or {}
