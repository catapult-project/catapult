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


def _DoNothingHandler(_elapsed_time):
  pass


class InspectorWebsocketUnittest(unittest.TestCase):

  def setUp(self):
    self._mock_timer = simple_mock.MockTimer(inspector_websocket)

  def tearDown(self):
    self._mock_timer.Restore()

  def testDispatchNotification(self):
    inspector = inspector_websocket.InspectorWebsocket()
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent)
    fake_socket.AddResponse('{"method": "Test.foo"}', 5)
    inspector.DispatchNotifications()
    self.assertEqual(1, len(results))
    self.assertEqual('Test.foo', results[0]['method'])

  def testDispatchNotificationTimedOut(self):
    inspector = inspector_websocket.InspectorWebsocket()
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent)
    fake_socket.AddResponse('{"method": "Test.foo"}', 11)
    with self.assertRaises(
        websocket.WebSocketTimeoutException):
      inspector.DispatchNotifications(timeout=10)
    self.assertEqual(0, len(results))

  def testUnregisterDomain(self):
    inspector = inspector_websocket.InspectorWebsocket()
    fake_socket = FakeSocket(self._mock_timer)
    # pylint: disable=protected-access
    inspector._socket = fake_socket

    results = []
    def OnTestEvent(result):
      results.append(result)

    inspector.RegisterDomain('Test', OnTestEvent)
    inspector.RegisterDomain('Test2', OnTestEvent)
    inspector.UnregisterDomain('Test')

    fake_socket.AddResponse('{"method": "Test.foo"}', 5)
    fake_socket.AddResponse('{"method": "Test2.foo"}', 10)

    inspector.DispatchNotifications()
    self.assertEqual(0, len(results))

    inspector.DispatchNotifications()
    self.assertEqual(1, len(results))
    self.assertEqual('Test2.foo', results[0]['method'])

  def testUnregisterDomainWithUnregisteredDomain(self):
    inspector = inspector_websocket.InspectorWebsocket()
    with self.assertRaises(AssertionError):
      inspector.UnregisterDomain('Test')
