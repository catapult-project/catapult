# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import logging
import socket

from telemetry.core import exceptions
from telemetry.core import forwarders
from telemetry.core import util


class Error(Exception):
  """Base class for exceptions in this module."""
  pass


class PortsMismatchError(Error):
  """Raised when local and remote ports are not equal."""
  pass


class ConnectionError(Error):
  """Raised when unable to connect to local TCP ports."""
  pass


class DoNothingForwarderFactory(forwarders.ForwarderFactory):

  def Create(self, port_pairs):
    return DoNothingForwarder(port_pairs)


class DoNothingForwarder(forwarders.Forwarder):
  """Check that no forwarding is needed for the given port pairs.

  The local and remote ports must be equal. Otherwise, the "do nothing"
  forwarder does not make sense. (Raises PortsMismatchError.)

  Also, check that all TCP ports support connections.  (Raises ConnectionError.)
  """

  def __init__(self, port_pairs):
    super(DoNothingForwarder, self).__init__(port_pairs)
    self._CheckPortPairs()

  def _CheckPortPairs(self):
    # namedtuple._asdict() is a public method. The method starts with an
    # underscore to avoid conflicts with attribute names. pylint: disable=W0212
    for protocol, port_pair in self._port_pairs._asdict().items():
      if not port_pair:
        continue
      local_port, remote_port = port_pair
      if local_port != remote_port:
        raise PortsMismatchError('Local port forwarding is not supported')
      if protocol == 'dns':
        logging.debug('Connection test SKIPPED for DNS: %s:%d',
                      self.host_ip, local_port)
        continue
      try:
        self._WaitForConnectionEstablished(
            (self.host_ip, local_port), timeout=10)
        logging.debug(
            'Connection test succeeded for %s: %s:%d',
            protocol.upper(), self.host_ip, local_port)
      except exceptions.TimeoutException:
        raise ConnectionError(
            'Unable to connect to %s address: %s:%d',
            protocol.upper(), self.host_ip, local_port)

  def _WaitForConnectionEstablished(self, address, timeout):
    def CanConnect():
      with contextlib.closing(socket.socket()) as s:
        return s.connect_ex(address) == 0
    util.WaitFor(CanConnect, timeout)
