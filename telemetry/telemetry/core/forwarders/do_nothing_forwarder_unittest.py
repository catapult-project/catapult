# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core.forwarders import do_nothing_forwarder


class TestDoNothingForwarder(do_nothing_forwarder.DoNothingForwarder):
  """Override _WaitForConnect to avoid actual socket connection."""

  def __init__(self, port_pairs):
    self.connected_addresses = []
    super(TestDoNothingForwarder, self).__init__(port_pairs)

  def _WaitForConnectionEstablished(self, address, timeout):
    self.connected_addresses.append(address)


class TestErrorDoNothingForwarder(do_nothing_forwarder.DoNothingForwarder):
  """Simulate a connection error."""

  def _WaitForConnectionEstablished(self, address, timeout):
    raise exceptions.TimeoutException


class CheckPortPairsTest(unittest.TestCase):
  def testChecksOnlyHttpHttps(self):
    port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(80, 80),
        https=forwarders.PortPair(443, 443),
        dns=forwarders.PortPair(53, 53))
    f = TestDoNothingForwarder(port_pairs)
    expected_connected_addresses = [
        ('127.0.0.1', 80),
        ('127.0.0.1', 443),
        # Port 53 is skipped because it is UDP and does not support connections.
        ]
    self.assertEqual(expected_connected_addresses, f.connected_addresses)

  def testNoDnsStillChecksHttpHttps(self):
    port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(5566, 5566),
        https=forwarders.PortPair(7788, 7788),
        dns=None)
    f = TestDoNothingForwarder(port_pairs)
    expected_connected_addresses = [
        ('127.0.0.1', 5566),
        ('127.0.0.1', 7788),
        ]
    self.assertEqual(expected_connected_addresses, f.connected_addresses)

  def testPortMismatchRaisesPortsMismatchError(self):
    # The do_nothing_forward cannot forward from one port to another.
    port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(80, 80),
        https=forwarders.PortPair(8443, 443),
        dns=None)
    with self.assertRaises(do_nothing_forwarder.PortsMismatchError):
      TestDoNothingForwarder(port_pairs)

  def testConnectionTimeoutRaisesConnectionError(self):
    port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(80, 80),
        https=forwarders.PortPair(8443, 443),
        dns=None)
    with self.assertRaises(do_nothing_forwarder.ConnectionError):
      TestErrorDoNothingForwarder(port_pairs)
