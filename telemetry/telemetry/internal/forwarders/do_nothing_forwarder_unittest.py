# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

from telemetry.internal.forwarders import do_nothing_forwarder

import py_utils


class TestDoNothingForwarder(do_nothing_forwarder.DoNothingForwarder):
  """Override _WaitForConnect to avoid actual socket connection."""

  def __init__(self, local_port, remote_port):
    self.connected_ports = []
    super(TestDoNothingForwarder, self).__init__(local_port, remote_port)

  def _WaitForConnectionEstablished(self):
    self.connected_ports.append(self.local_port)


class CheckPortPairsTest(unittest.TestCase):
  def testBasicCheck(self):
    f = TestDoNothingForwarder(local_port=80, remote_port=80)
    self.assertEqual(f.connected_ports, [80])
    self.assertEqual(f.local_port, f.remote_port)

  def testDefaultLocalPort(self):
    f = TestDoNothingForwarder(local_port=None, remote_port=80)
    self.assertEqual(f.connected_ports, [80])
    self.assertEqual(f.local_port, f.remote_port)

  def testDefaultRemotePort(self):
    f = TestDoNothingForwarder(local_port=42, remote_port=0)
    self.assertEqual(f.connected_ports, [42])
    self.assertEqual(f.local_port, f.remote_port)

  def testMissingPortsRaisesError(self):
    # At least one of the two ports must be given
    with self.assertRaises(AssertionError):
      TestDoNothingForwarder(local_port=None, remote_port=None)

  def testPortMismatchRaisesPortsMismatchError(self):
    # The do_nothing_forward cannot forward from one port to another.
    with self.assertRaises(do_nothing_forwarder.PortsMismatchError):
      TestDoNothingForwarder(local_port=80, remote_port=81)

  @mock.patch('py_utils.WaitFor')
  def testConnectionTimeoutRaisesConnectionError(self, wait_for):
    # Simulate a connection error.
    wait_for.side_effect = py_utils.TimeoutException

    with self.assertRaises(do_nothing_forwarder.ConnectionError):
      do_nothing_forwarder.DoNothingForwarder(local_port=80, remote_port=80)
