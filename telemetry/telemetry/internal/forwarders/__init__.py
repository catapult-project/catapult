# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections


PortPair = collections.namedtuple('PortPair', ['local_port', 'remote_port'])
PortPairs = collections.namedtuple('PortPairs', ['http', 'https', 'dns'])


class ForwarderFactory(object):

  def Create(self, port_pairs):
    """Creates a forwarder that maps remote (device) <-> local (host) ports.

    Args:
      port_pairs: A PortPairs instance that consists of a PortPair mapping
          for each protocol. http is required. https and dns may be None.
    """
    raise NotImplementedError()

  @property
  def host_ip(self):
    return '127.0.0.1'

  @property
  def does_forwarder_override_dns(self):
    return False


class Forwarder(object):

  def __init__(self, port_pairs):
    assert port_pairs.http, 'HTTP port mapping is required.'
    self._port_pairs = PortPairs(*[
        PortPair(p.local_port, p.remote_port or p.local_port)
        if p else None for p in port_pairs])

  @property
  def host_port(self):
    return self._port_pairs.http.remote_port

  @property
  def host_ip(self):
    return '127.0.0.1'

  @property
  def port_pairs(self):
    return self._port_pairs

  @property
  def url(self):
    assert self.host_ip and self.host_port
    return 'http://%s:%i' % (self.host_ip, self.host_port)

  def Close(self):
    self._port_pairs = None
