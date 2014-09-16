# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.unittest import simple_mock
from telemetry.core.backends.chrome import inspector_websocket
from telemetry.core.backends.chrome import websocket


class FakeSocket(object):
  """ A fake socket that:
        + Receives first package of data after 10 second in the first recv().
        + Receives second package of data after 10 second in the second recv().
        + Raises a websocket.WebSocketTimeoutException after 15 seconds in the
          third recv().
        + Raises a websocket.WebSocketTimeoutException after 15 seconds in the
          fourth recv().
        + Receives third package of data after 10 second in the fifth recv().
        + Receives last package of data (containing 'method') after 10 second
          in the last recv().
  """
  def __init__(self, mock_timer):
    self._mock_timer = mock_timer
    self._recv_counter = 0

  def recv(self):
    self._recv_counter += 1
    if self._recv_counter == 1:
      self._mock_timer.SetTime(10)
      return '["foo"]'
    elif self._recv_counter == 2:
      self._mock_timer.SetTime(20)
      return '["bar"]'
    elif self._recv_counter == 3:
      self._mock_timer.SetTime(35)
      raise websocket.WebSocketTimeoutException()
    elif self._recv_counter == 4:
      self._mock_timer.SetTime(50)
      raise websocket.WebSocketTimeoutException()
    elif self._recv_counter == 5:
      self._mock_timer.SetTime(60)
      return '["baz"]'
    elif self._recv_counter == 6:
      self._mock_timer.SetTime(70)
      return '["method"]'

  def settimeout(self, timeout):
    pass


def _ReraiseExceptionErrorHandler(_elapsed_time):
  raise


def _DoNothingExceptionErrorHandler(_elapsed_time):
  pass


class InspectorWebsocketUnittest(unittest.TestCase):

  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(inspector_websocket)

  def tearDown(self):
    self._mock_timer.Restore()

  def testDispatchNotificationUntilDoneTimedOutOne(self):
    inspector = inspector_websocket.InspectorWebsocket(
      notification_handler=lambda data: True,
      error_handler=_ReraiseExceptionErrorHandler)
    inspector._socket = FakeSocket(self._mock_timer)
    # The third call to socket.recv() will take 15 seconds without any data
    # received, hence the below call will raise a
    # DispatchNotificationsUntilDoneTimeoutException.
    with self.assertRaises(
      inspector_websocket.DispatchNotificationsUntilDoneTimeoutException):
      inspector.DispatchNotificationsUntilDone(12)

  def testDispatchNotificationUntilDoneTimedOutTwo(self):
    inspector = inspector_websocket.InspectorWebsocket(
      notification_handler=lambda data: True,
      error_handler=_DoNothingExceptionErrorHandler)
    inspector._socket = FakeSocket(self._mock_timer)
    # The third and forth calls to socket.recv() will take 30 seconds without
    # any data received, hence the below call will raise a
    # DispatchNotificationsUntilDoneTimeoutException.
    with self.assertRaises(
      inspector_websocket.DispatchNotificationsUntilDoneTimeoutException):
      inspector.DispatchNotificationsUntilDone(29)

  def testDispatchNotificationUntilDoneNotTimedOut(self):
    inspector = inspector_websocket.InspectorWebsocket(
    notification_handler=lambda data: True,
    error_handler=_ReraiseExceptionErrorHandler)
    inspector._socket = FakeSocket(self._mock_timer)
    # Even though it takes 70 seconds to receive all the data, the call below
    # will succeed since there are no interval which the previous data package
    # received and the next failed data receiving attempt was greater than
    # 30 seconds.
    inspector.DispatchNotificationsUntilDone(31)
