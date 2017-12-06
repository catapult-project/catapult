# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import subprocess
import tempfile

from telemetry.internal import forwarders
from telemetry.internal.forwarders import do_nothing_forwarder

import py_utils


class CrOsForwarderFactory(forwarders.ForwarderFactory):

  def __init__(self, cri):
    super(CrOsForwarderFactory, self).__init__()
    self._cri = cri

  def Create(self, local_port, remote_port, reverse=False):
    if self._cri.local:
      return do_nothing_forwarder.DoNothingForwarder(local_port, remote_port)
    return CrOsSshForwarder(self._cri, local_port, remote_port,
                            use_remote_port_forwarding=not reverse)


class CrOsSshForwarder(forwarders.Forwarder):

  def __init__(self, cri, local_port, remote_port, use_remote_port_forwarding):
    super(CrOsSshForwarder, self).__init__()
    # TODO(#1977): Move call to after forwarding has actually started.
    self._StartedForwarding(local_port, remote_port)
    self._cri = cri
    self._proc = None
    self._remote_port = None
    forwarding_args = self._ForwardingArgs(
        use_remote_port_forwarding, self.host_ip, self._port_pair)
    err_file = tempfile.NamedTemporaryFile()
    self._proc = subprocess.Popen(
        self._cri.FormSSHCommandLine(['-NT'], forwarding_args,
                                     port_forward=use_remote_port_forwarding),
        stdout=subprocess.PIPE,
        stderr=err_file,
        stdin=subprocess.PIPE,
        shell=False)
    def _get_remote_port(err_file):
      # When we specify the remote port '0' in ssh remote port forwarding,
      # the remote ssh server should return the port it binds to in stderr.
      # e.g. 'Allocated port 42360 for remote forward to localhost:12345',
      # the port 42360 is the port created remotely and the traffic to the
      # port will be relayed to localhost port 12345.
      line = err_file.readline()
      tokens = re.search(r'port (\d+) for remote forward to', line)
      if tokens:
        self._remote_port = int(tokens.group(1))
      return tokens

    if use_remote_port_forwarding and self._port_pair.remote_port == 0:
      with open(err_file.name, 'r') as err_file_reader:
        py_utils.WaitFor(lambda: _get_remote_port(err_file_reader), 60)

    py_utils.WaitFor(
        lambda: self._cri.IsHTTPServerRunningOnPort(self.remote_port), 60)
    err_file.close()
    logging.debug('Server started on %s:%d', self.host_ip, self.remote_port)

  # pylint: disable=unused-argument
  @staticmethod
  def _ForwardingArgs(use_remote_port_forwarding, host_ip, port_pair):
    if use_remote_port_forwarding:
      arg_format = '-R{remote_port}:{host_ip}:{local_port}'
    else:
      arg_format = '-L{local_port}:{host_ip}:{remote_port}'
    return [arg_format.format(host_ip=host_ip,
                              local_port=port_pair.local_port,
                              remote_port=port_pair.remote_port)]

  @property
  def remote_port(self):
    # Return remote port if it is resolved remotely.
    if self._remote_port:
      return self._remote_port
    return self._port_pair.remote_port

  def Close(self):
    if self._proc:
      self._proc.kill()
      self._proc = None
    super(CrOsSshForwarder, self).Close()
