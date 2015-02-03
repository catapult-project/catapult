# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from telemetry.core import platform
from telemetry.core.platform import cros_interface
from telemetry.core.platform import device


class CrOSDevice(device.Device):
  def __init__(self, host_name, ssh_port, ssh_identity=None):
    super(CrOSDevice, self).__init__(
        name='ChromeOs with host %s' % host_name,
        guid='cros:%s' % host_name)
    assert host_name and ssh_port
    self._host_name = host_name
    self._ssh_port = ssh_port
    self._ssh_identity = ssh_identity

  @classmethod
  def GetAllConnectedDevices(cls):
    return []

  @property
  def host_name(self):
    return self._host_name

  @property
  def ssh_port(self):
    return self._ssh_port

  @property
  def ssh_identity(self):
    return self._ssh_identity


def IsRunningOnCrOS():
  return platform.GetHostPlatform().GetOSName() == 'chromeos'


def FindAllAvailableDevices(options):
  """Returns a list of available device types.
  """
  if IsRunningOnCrOS():
    return [CrOSDevice('localhost', -1)]

  if options.cros_remote == None:
    logging.debug('No --remote specified, will not probe for CrOS.')
    return []

  if not cros_interface.HasSSH():
    logging.debug('ssh not found. Cannot talk to CrOS devices.')
    return []

  return [CrOSDevice(options.cros_remote, options.cros_remote_ssh_port,
                     options.cros_ssh_identity)]
