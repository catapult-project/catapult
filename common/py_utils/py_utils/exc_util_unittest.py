# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import sys
import unittest

from py_utils import exc_util


class FakeConnectionError(Exception):
  pass


class FakeDisconnectionError(Exception):
  pass


class FakeProcessingError(Exception):
  pass


class FakeCleanupError(Exception):
  pass


class FaultyClient(object):
  def __init__(self, *args):
    self.failures = set(args)
    self.called = set()

  def Connect(self):
    self.called.add('Connect')
    if FakeConnectionError in self.failures:
      raise FakeConnectionError('Oops!')

  def Process(self):
    self.called.add('Process')
    if FakeProcessingError in self.failures:
      raise FakeProcessingError('Oops!')

  @exc_util.BestEffort
  def Disconnect(self):
    self.called.add('Disconnect')
    if FakeDisconnectionError in self.failures:
      raise FakeDisconnectionError('Oops!')

  @exc_util.BestEffort
  def Cleanup(self):
    self.called.add('Cleanup')
    if FakeCleanupError in self.failures:
      raise FakeCleanupError('Oops!')


class ReraiseTests(unittest.TestCase):
  def assertLogMatches(self, pattern):
    self.assertRegexpMatches(
        sys.stderr.getvalue(), pattern)  # pylint: disable=no-member

  def assertLogNotMatches(self, pattern):
    self.assertNotRegexpMatches(
        sys.stderr.getvalue(), pattern)  # pylint: disable=no-member

  def testTryRaisesExceptRaises(self):
    client = FaultyClient(FakeConnectionError, FakeDisconnectionError)

    # The connection error reaches the top level, while the disconnection
    # error is logged.
    with self.assertRaises(FakeConnectionError):
      try:
        client.Connect()
      except:
        client.Disconnect()
        raise

    self.assertLogMatches(re.compile(
        r'While handling a FakeConnectionError, .* was also raised:\n'
        r'Traceback \(most recent call last\):\n'
        r'.*\n'
        r'FakeDisconnectionError: Oops!\n', re.DOTALL))
    self.assertItemsEqual(client.called, ['Connect', 'Disconnect'])

  def testTryRaisesExceptDoesnt(self):
    client = FaultyClient(FakeConnectionError)

    # The connection error reaches the top level, disconnecting did not raise
    # an exception (so nothing is logged).
    with self.assertRaises(FakeConnectionError):
      try:
        client.Connect()
      except:
        client.Disconnect()
        raise

    self.assertLogNotMatches('FakeDisconnectionError')
    self.assertItemsEqual(client.called, ['Connect', 'Disconnect'])

  def testTryPassesNoException(self):
    client = FaultyClient(FakeDisconnectionError)

    # If there is no connection error, the except clause is not called (even if
    # it would have raised an exception).
    try:
      client.Connect()
    except:
      client.Disconnect()
      raise

    self.assertLogNotMatches('FakeConnectionError')
    self.assertLogNotMatches('FakeDisconnectionError')
    self.assertItemsEqual(client.called, ['Connect'])

  def testTryRaisesFinallyRaises(self):
    worker = FaultyClient(FakeProcessingError, FakeCleanupError)

    # The processing error reaches the top level, the cleanup error is logged.
    with self.assertRaises(FakeProcessingError):
      try:
        worker.Process()
      except:
        raise  # Needed for Cleanup to know if an exception is handled.
      finally:
        worker.Cleanup()

    self.assertLogMatches(re.compile(
        r'While handling a FakeProcessingError, .* was also raised:\n'
        r'Traceback \(most recent call last\):\n'
        r'.*\n'
        r'FakeCleanupError: Oops!\n', re.DOTALL))
    self.assertItemsEqual(worker.called, ['Process', 'Cleanup'])

  def testTryRaisesFinallyDoesnt(self):
    worker = FaultyClient(FakeProcessingError)

    # The processing error reaches the top level, the cleanup code runs fine.
    with self.assertRaises(FakeProcessingError):
      try:
        worker.Process()
      except:
        raise  # Needed for Cleanup to know if an exception is handled.
      finally:
        worker.Cleanup()

    self.assertLogNotMatches('FakeProcessingError')
    self.assertLogNotMatches('FakeCleanupError')
    self.assertItemsEqual(worker.called, ['Process', 'Cleanup'])

  def testTryPassesFinallyRaises(self):
    worker = FaultyClient(FakeCleanupError)

    # The processing code runs fine, the cleanup code raises an exception
    # which reaches the top level.
    with self.assertRaises(FakeCleanupError):
      try:
        worker.Process()
      except:
        raise  # Needed for Cleanup to know if an exception is handled.
      finally:
        worker.Cleanup()

    self.assertLogNotMatches('FakeProcessingError')
    self.assertLogNotMatches('FakeCleanupError')
    self.assertItemsEqual(worker.called, ['Process', 'Cleanup'])

  def testTryRaisesExceptRaisesFinallyRaises(self):
    worker = FaultyClient(
        FakeProcessingError, FakeDisconnectionError, FakeCleanupError)

    # Chaining try-except-finally works fine. Only the processing error reaches
    # the top level; the other two are logged.
    with self.assertRaises(FakeProcessingError):
      try:
        worker.Process()
      except:
        worker.Disconnect()
        raise
      finally:
        worker.Cleanup()

    self.assertLogMatches('FakeDisconnectionError')
    self.assertLogMatches('FakeCleanupError')
    self.assertItemsEqual(worker.called, ['Process', 'Disconnect', 'Cleanup'])
