# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import forwarders
from telemetry.core import wpr_server


# pylint: disable=W0212
class ForwarderPortPairsTest(unittest.TestCase):
  def testNoRemotePortsGivesLocalToLocal(self):
    started_ports = (8080, 8443, None)
    wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(0, 8080),
        https=forwarders.PortPair(0, 8443),
        dns=None)
    expected_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(8080, 8080),
        https=forwarders.PortPair(8443, 8443),
        dns=None)
    self.assertEqual(
        expected_port_pairs,
        wpr_server.ReplayServer._ForwarderPortPairs(started_ports,
                                                    wpr_port_pairs))

  def testNetsimPortsGives(self):
    started_ports = (8888, 4343, 5353)
    wpr_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(0, 80),
        https=forwarders.PortPair(0, 443),
        dns=forwarders.PortPair(0, 53))
    expected_port_pairs = forwarders.PortPairs(
        http=forwarders.PortPair(8888, 80),
        https=forwarders.PortPair(4343, 443),
        dns=forwarders.PortPair(5353, 53))
    self.assertEqual(
        expected_port_pairs,
        wpr_server.ReplayServer._ForwarderPortPairs(started_ports,
                                                    wpr_port_pairs))
