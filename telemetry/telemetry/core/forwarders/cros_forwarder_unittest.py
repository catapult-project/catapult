# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core import forwarders
from telemetry.core.forwarders import cros_forwarder

# pylint: disable=W0212
class ForwardingArgsTest(unittest.TestCase):
  port_pairs = forwarders.PortPairs(
      http=forwarders.PortPair(111, 222),
      https=forwarders.PortPair(333, 444),
      dns=None)

  def testForwardingArgsReverse(self):
    forwarding_args = cros_forwarder.CrOsSshForwarder._ForwardingArgs(
        use_remote_port_forwarding=True, host_ip='5.5.5.5',
        port_pairs=self.port_pairs)
    self.assertEqual(
        ['-R222:5.5.5.5:111', '-R444:5.5.5.5:333'],
        forwarding_args)

  def testForwardingArgs(self):
    forwarding_args = cros_forwarder.CrOsSshForwarder._ForwardingArgs(
        use_remote_port_forwarding=False, host_ip='2.2.2.2',
        port_pairs=self.port_pairs)
    self.assertEqual(
        ['-L111:2.2.2.2:222', '-L333:2.2.2.2:444'],
        forwarding_args)
