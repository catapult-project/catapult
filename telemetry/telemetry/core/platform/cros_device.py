# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core.platform import device


class CrOSDevice(device.Device):
  def __init__(self, host_name, ssh_identity=None):
    super(CrOSDevice, self).__init__(
        name='ChromeOs with host %s' % host_name,
        guid='cros:%s' % host_name)
    assert host_name
    self._host_name = host_name
    self._ssh_identity = ssh_identity

  @classmethod
  def GetAllConnectedDevices(cls):
    return []

  @property
  def host_name(self):
    return self._host_name

  @property
  def ssh_identity(self):
    return self._ssh_identity
