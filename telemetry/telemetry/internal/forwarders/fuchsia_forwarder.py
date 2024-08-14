# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from telemetry.core.fuchsia_interface import include_fuchsia_package
from telemetry.internal import forwarders


class FuchsiaForwarderFactory(forwarders.ForwarderFactory):
  def __init__(self, command_runner):
    super().__init__()
    self._target_id = command_runner.target_id

  def Create(self, local_port, remote_port, reverse=False):
    return FuchsiaSshForwarder(self._target_id,
                               local_port,
                               remote_port,
                               port_forward=not reverse)


# pylint: disable=import-error, import-outside-toplevel
class FuchsiaSshForwarder(forwarders.Forwarder):

  def __init__(self, target_id, local_port, remote_port, port_forward):
    """Sets up ssh port forwarding betweeen a Fuchsia device and the host.

    Args:
      local_port: Port on the host.
      remote_port: Port on the Fuchsia device.
      port_forward: Determines the direction of the connection."""
    super().__init__()

    include_fuchsia_package()
    from common import get_ssh_address

    # The original parameters are needed for the port forwarding cancellation.
    self._target_addr = get_ssh_address(target_id)
    self._port_forward = port_forward

    if port_forward:
      assert not remote_port, \
          'Specifying a remote_port with port-forward is not supported yet.'
      from test_server import port_forward
      remote_port = port_forward(self._target_addr, local_port)
      self._host_port = local_port
      self._fuchsia_port = 0
    else:
      from test_server import port_backward
      local_port = port_backward(self._target_addr, remote_port, local_port)
      self._host_port = local_port
      self._fuchsia_port = remote_port

    self._StartedForwarding(local_port, remote_port)

  def Close(self):
    include_fuchsia_package()
    from test_server import cancel_port_forwarding
    cancel_port_forwarding(self._target_addr, self._fuchsia_port,
                           self._host_port, self._port_forward)
    super().Close()
