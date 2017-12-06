# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.internal.forwarders import do_nothing_forwarder

import py_utils


class TestDoNothingForwarder(do_nothing_forwarder.DoNothingForwarder):
  """Override _WaitForConnect to avoid actual socket connection."""

  def __init__(self, local_port, remote_port):
    self.connected_addresses = []
    super(TestDoNothingForwarder, self).__init__(local_port, remote_port)

  def _WaitForConnectionEstablished(self, address, timeout):
    self.connected_addresses.append(address)


class TestErrorDoNothingForwarder(do_nothing_forwarder.DoNothingForwarder):
  """Simulate a connection error."""

  def _WaitForConnectionEstablished(self, address, timeout):
    raise py_utils.TimeoutException


class CheckPortPairsTest(unittest.TestCase):
  def testBasicCheck(self):
    f = TestDoNothingForwarder(local_port=80, remote_port=80)
    expected_connected_addresses = [
        ('127.0.0.1', 80),
        ]
    self.assertEqual(expected_connected_addresses, f.connected_addresses)

  def testPortMismatchRaisesPortsMismatchError(self):
    # The do_nothing_forward cannot forward from one port to another.
    with self.assertRaises(do_nothing_forwarder.PortsMismatchError):
      TestDoNothingForwarder(local_port=80, remote_port=81)

  def testConnectionTimeoutRaisesConnectionError(self):
    with self.assertRaises(do_nothing_forwarder.ConnectionError):
      TestErrorDoNothingForwarder(local_port=80, remote_port=80)
