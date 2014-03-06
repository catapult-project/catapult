# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import subprocess

from telemetry.core import forwarders
from telemetry.core import util
from telemetry.core.forwarders import do_nothing_forwarder


class CrOsForwarderFactory(forwarders.ForwarderFactory):

  def __init__(self, cri):
    super(CrOsForwarderFactory, self).__init__()
    self._cri = cri

  def Create(self, port_pairs, forwarding_flag='R'):  # pylint: disable=W0221
    if self._cri.local:
      return do_nothing_forwarder.DoNothingForwarder(port_pairs)
    return CrOsSshForwarder(self._cri, forwarding_flag, port_pairs)


class CrOsSshForwarder(forwarders.Forwarder):

  def __init__(self, cri, forwarding_flag, port_pairs):
    super(CrOsSshForwarder, self).__init__(port_pairs)
    self._cri = cri
    self._proc = None
    self._forwarding_flag = forwarding_flag

    if self._forwarding_flag == 'R':
      command_line = ['-%s%i:%s:%i' % (self._forwarding_flag,
                                       port_pair.remote_port,
                                       self.host_ip,
                                       port_pair.local_port)
                      for port_pair in port_pairs if port_pair]
    else:
      command_line = ['-%s%i:%s:%i' % (self._forwarding_flag,
                                       port_pair.local_port,
                                       self.host_ip,
                                       port_pair.remote_port)
                      for port_pair in port_pairs if port_pair]
      logging.debug('Forwarding to localhost:%d', port_pairs[0].local_port)
    self._proc = subprocess.Popen(
        self._cri.FormSSHCommandLine(['sleep', '999999999'], command_line),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        shell=False)
    util.WaitFor(
        lambda: self._cri.IsHTTPServerRunningOnPort(self.host_port), 60)
    logging.debug('Server started on %s:%d', self.host_ip, self.host_port)

  @property
  def host_port(self):
    return self._port_pairs.http.remote_port

  def Close(self):
    if self._proc:
      self._proc.kill()
      self._proc = None
    super(CrOsSshForwarder, self).Close()
