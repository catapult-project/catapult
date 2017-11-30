# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections


# TODO(#1977): Remove when no longer used by fowarder implementations.
_PortPair = collections.namedtuple('PortPair', ['local_port', 'remote_port'])


class ForwarderFactory(object):

  def Create(self, local_port, remote_port, reverse=False):
    """Creates a forwarder to map a local (host) with a remote (device) port.

    By default this means mapping a known local_port with a remote_port. If the
    remote_port missing (e.g. 0 or None) then the forwarder will choose an
    available port on the device.

    Conversely, when reverse=True, a known remote_port is mapped to a
    local_port and, if this is missing, then the forwarder will choose an
    available port on the host.

    # TODO(#1977): Ensure all implementations fully support the previous
    # description regarding missing ports.

    Args:
      local_port: An http port on the local host.
      remote_port: An http port on the remote device.
      reverse: A Boolean indicating the direction of the mapping.
    """
    raise NotImplementedError()

  @property
  def host_ip(self):
    return '127.0.0.1'


class Forwarder(object):

  def __init__(self, port_pair):
    assert port_pair, 'Port mapping is required.'
    self._port_pair = port_pair
    self._forwarding = True

  @property
  def host_ip(self):
    return '127.0.0.1'

  @property
  def local_port(self):
    return self._port_pair.local_port

  @property
  def remote_port(self):
    return self._port_pair.remote_port

  def Close(self):
    self._port_pair = None
    self._forwarding = False
