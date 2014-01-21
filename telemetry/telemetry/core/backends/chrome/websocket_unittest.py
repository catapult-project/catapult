# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import socket
import unittest

from telemetry.core.backends.chrome import websocket

class TestWebSocket(unittest.TestCase):
  def testExports(self):
    self.assertNotEqual(websocket.create_connection, None)
    self.assertNotEqual(websocket.WebSocketException, None)
    self.assertNotEqual(websocket.WebSocketTimeoutException, None)

  def testSockOpts(self):
    ws = websocket.create_connection('ws://echo.websocket.org')
    self.assertNotEquals(
        ws.sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR), 0)
    ws = websocket.create_connection(
        'ws://echo.websocket.org',
        sockopt=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)])
    self.assertNotEquals(
        ws.sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR), 0)
    self.assertNotEquals(
        ws.sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY), 0)
