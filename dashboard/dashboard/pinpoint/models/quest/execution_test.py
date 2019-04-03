# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models.quest import execution


class _ExecutionStub(execution.Execution):

  def _AsDict(self):
    return {'details key': 'details value'}

  def _Poll(self):
    raise NotImplementedError()


class ExecutionException(_ExecutionStub):
  """This Execution always fails with a fatal exception on first Poll()."""

  def _Poll(self):
    raise StandardError('An unhandled, unexpected exception.')


class ExecutionException2(_ExecutionStub):
  """This Execution always fails on first Poll()."""

  def _Poll(self):
    raise errors.RecoverableError()


class ExecutionFail(_ExecutionStub):
  """This Execution always fails on first Poll()."""

  def _Poll(self):
    raise Exception('Expected error for testing.')


class ExecutionFail2(_ExecutionStub):
  """This Execution always fails on first Poll()."""

  def _Poll(self):
    raise Exception('A different expected error for testing.')


class ExecutionPass(_ExecutionStub):
  """This Execution always completes on first Poll()."""

  def _Poll(self):
    self._Complete(result_arguments={'arg key': 'arg value'},
                   result_values=(1, 2, 3))


class ExecutionSpin(_ExecutionStub):
  """This Execution never completes."""

  def _Poll(self):
    pass


class ExecutionTest(unittest.TestCase):

  def testExecution(self):
    e = execution.Execution()

    self.assertFalse(e.completed)
    self.assertFalse(e.failed)
    self.assertIsNone(e.exception)
    self.assertEqual(e.result_values, ())
    self.assertEqual(e.result_arguments, {})

    with self.assertRaises(NotImplementedError):
      e.AsDict()
    with self.assertRaises(NotImplementedError):
      e.Poll()

  def testExecutionCompleted(self):
    e = ExecutionPass()
    e.Poll()

    with self.assertRaises(AssertionError):
      e.Poll()

    self.assertTrue(e.completed)
    self.assertFalse(e.failed)
    self.assertIsNone(e.exception)
    self.assertEqual(e.result_values, (1, 2, 3))
    self.assertEqual(e.result_arguments, {'arg key': 'arg value'})
    expected = {
        'completed': True,
        'exception': None,
        'details': {'details key': 'details value'},
    }
    self.assertEqual(e.AsDict(), expected)

  def testExecutionFailed(self):
    e = ExecutionFail()
    e.Poll()

    self.assertTrue(e.completed)
    self.assertTrue(e.failed)
    expected = 'Exception: Expected error for testing.'
    self.assertEqual(e.exception.splitlines()[-1], expected)
    self.assertEqual(e.result_values, ())
    self.assertEqual(e.result_arguments, {})

  def testExecutionException(self):
    e = ExecutionException()
    with self.assertRaises(StandardError):
      e.Poll()

  def testExecutionRecoverableException(self):
    e = ExecutionException2()
    with self.assertRaises(errors.RecoverableError):
      e.Poll()
