# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.internal.util import atexit_with_log
import logging
import subprocess

from telemetry.internal import forwarders

try:
  from devil.android import forwarder
except ImportError:
  forwarder = None


class AndroidForwarderFactory(forwarders.ForwarderFactory):

  def __init__(self, device):
    super(AndroidForwarderFactory, self).__init__()
    self._device = device

  def Create(self, port_pairs):
    try:
      return AndroidForwarder(self._device, port_pairs)
    except Exception:
      try:
        logging.warning('Failed to create forwarder. '
                        'Currently forwarded connections:')
        for line in self._device.adb.ForwardList().splitlines():
          logging.warning('  %s', line)
      except Exception:
        logging.warning('Exception raised while listing forwarded connections.')

      logging.warning('Device tcp sockets in use:')
      try:
        for line in self._device.ReadFile('/proc/net/tcp', as_root=True,
                                          force_pull=True).splitlines():
          logging.warning('  %s', line)
      except Exception:
        logging.warning('Exception raised while listing tcp sockets.')

      logging.warning('Alive webpagereplay instances:')
      try:
        for line in subprocess.check_output(['ps', '-ef']).splitlines():
          if 'webpagereplay' in line:
            logging.warning('  %s', line)
      except Exception:
        logging.warning('Exception raised while listing WPR intances.')

      raise


class AndroidForwarder(forwarders.Forwarder):

  def __init__(self, device, port_pairs):
    super(AndroidForwarder, self).__init__(port_pairs)
    self._device = device
    forwarder.Forwarder.Map([(p.remote_port, p.local_port)
                             for p in port_pairs if p], self._device)
    self._port_pairs = forwarders.PortPairs(*[
        forwarders.PortPair(
            p.local_port,
            forwarder.Forwarder.DevicePortForHostPort(p.local_port))
        if p else None for p in port_pairs])
    atexit_with_log.Register(self.Close)
    # TODO(tonyg): Verify that each port can connect to host.

  def Close(self):
    if self._forwarding:
      for port_pair in self._port_pairs:
        if port_pair:
          forwarder.Forwarder.UnmapDevicePort(
              port_pair.remote_port, self._device)
      super(AndroidForwarder, self).Close()
