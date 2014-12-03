# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.backends.chrome_inspector import inspector_websocket
from telemetry.core.backends.chrome_inspector import websocket
from telemetry.unittest_util import simple_mock


class FakeSocket(object):
  """A fake websocket that allows test to send random data."""
  def __init__(self, mock_timer):
    self._mock_timer = mock_timer
    self._responses = []
    self._timeout = None

  def AddResponse(self, response, time):
    if self._responses:
      assert self._responses[-1][1] < time, (
          'Current response is scheduled earlier than previous response.')
    self._responses.append((response, time))

  def recv(self):
    if not self._responses:
      raise Exception('No more recorded responses.')

    response, time = self._responses.pop(0)
    current_time = self._mock_timer.time()
    if self._timeout is not None and time - current_time > self._timeout:
      self._mock_timer.SetTime(current_time + self._timeout + 1)
      raise websocket.WebSocketTimeoutException()

    self._mock_timer.SetTime(time)
    return response

  def settimeout(self, timeout):
    self._timeout = timeout


def _ReraiseExceptionErrorHandler(_elapsed_time):
  raise


def _DoNothingHandler(_elapsed_time):
  pass


class InspectorWebsocketUnittest(unittest.TestCase):

  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(inspector_websocket)

  def tearDown(self):
    self._mock_timer.Restore()

  def testDispatchNotification(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    fake_socket.AddResponse('{"method": "Test.foo"}', 5)
    inspector.DispatchNotifications()
    self.assertEqual(1, len(results))
    self.assertEqual('Test.foo', results[0]['method'])

  def testDispatchNotificationTimedOut(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    fake_socket.AddResponse('{"method": "Test.foo"}', 11)
    with self.assertRaises(
        websocket.WebSocketTimeoutException):
      inspector.DispatchNotifications(timeout=10)
    self.assertEqual(0, len(results))

  def testDispatchNotificationUntilDoneTimedOut2(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    inspector._socket = fake_socket # pylint: disable=W0212

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    # The third call to socket.recv() will take 15 seconds without any data
    # received, hence the below call will raise a
    # DispatchNotificationsUntilDoneTimeoutException.
    fake_socket.AddResponse('{"method": "Test.foo"}', 10)
    fake_socket.AddResponse('{"method": "Test.bar"}', 20)
    fake_socket.AddResponse('{"method": "Test.baz"}', 35)
    with self.assertRaises(
        inspector_websocket.DispatchNotificationsUntilDoneTimeoutException):
      inspector.DispatchNotificationsUntilDone(12)
    self.assertEqual(2, len(results))

  def testDispatchNotificationsUntilDone(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)
      return len(results) > 2

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    # Even though it takes 70 seconds to receive all the data, the call below
    # will succeed since there are no interval which the previous data package
    # received and the next failed data receiving attempt was greater than
    # 30 seconds.
    fake_socket.AddResponse('{"method": "Test.foo"}', 10)
    fake_socket.AddResponse('{"method": "Test.bar"}', 20)
    fake_socket.AddResponse('{"method": "Test.baz"}', 35)
    fake_socket.AddResponse('{"method": "Test.qux"}', 50)
    fake_socket.AddResponse('{"method": "Test.baz"}', 60)
    fake_socket.AddResponse('{"method": "Test.foo"}', 70)
    inspector.DispatchNotificationsUntilDone(31)
    self.assertEqual(3, len(results))
    self.assertEqual('Test.baz', results[2]['method'])

  def testDispatchNotificationsUntilDoneTimedOut(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    fake_socket.AddResponse('{"method": "Test.foo"}', 5)
    fake_socket.AddResponse('{"method": "Test.bar"}', 16)
    fake_socket.AddResponse('{"method": "Test.baz"}', 20)
    with self.assertRaises(
        inspector_websocket.DispatchNotificationsUntilDoneTimeoutException):
      inspector.DispatchNotificationsUntilDone(10)
    self.assertEqual(1, len(results))

  def testUnregisterDomain(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent, _DoNothingHandler)
    inspector.RegisterDomain('Test2', OnTestEvent, _DoNothingHandler)
    inspector.UnregisterDomain('Test')

    fake_socket.AddResponse('{"method": "Test.foo"}', 5)
    fake_socket.AddResponse('{"method": "Test2.foo"}', 10)

    inspector.DispatchNotifications()
    self.assertEqual(0, len(results))

    inspector.DispatchNotifications()
    self.assertEqual(1, len(results))
    self.assertEqual('Test2.foo', results[0]['method'])

  def testUnregisterDomainWithUnregisteredDomain(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)
    with self.assertRaises(AssertionError):
      inspector.UnregisterDomain('Test')

  def testRegisterDomainWillCloseHandler(self):
    inspector = inspector_websocket.InspectorWebsocket(
        error_handler=_ReraiseExceptionErrorHandler)

    results = []
    def OnClose():
      results.append(1)
    results2 = []
    def OnClose2():
      results2.append(1)

    inspector.RegisterDomain('Test', _DoNothingHandler, OnClose)
    inspector.RegisterDomain('Test2', _DoNothingHandler, OnClose2)
    inspector.RegisterDomain('Test3', _DoNothingHandler)
    inspector.Disconnect()
    self.assertEqual(1, len(results))
    self.assertEqual(1, len(results2))
