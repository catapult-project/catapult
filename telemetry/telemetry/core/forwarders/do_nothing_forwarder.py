# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket

from telemetry.core import forwarders
from telemetry.core import util


class DoNothingForwarderFactory(forwarders.ForwarderFactory):

  def Create(self, port_pairs):
    return DoNothingForwarder(port_pairs)


class DoNothingForwarder(forwarders.Forwarder):

  def __init__(self, port_pairs):
    super(DoNothingForwarder, self).__init__(port_pairs)

    for port_pair in port_pairs:
      if not port_pair:
        continue
      local_port, remote_port = port_pair
      assert local_port == remote_port, 'Local port forwarding is not supported'
      def IsStarted():
        return not socket.socket().connect_ex((self.host_ip, self.host_port))
      util.WaitFor(IsStarted, 10)
      logging.debug('Server started on %s:%d' % (self.host_ip, self.host_port))
