# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import device


class TrybotDevice(device.Device):
  def __init__(self):
    super(TrybotDevice, self).__init__(name='trybot', guid='trybot')

  @classmethod
  def GetAllConnectedDevices(cls):
    return []


def FindAllAvailableDevices(_):
  """Returns a list of available devices.
  """
  return [TrybotDevice()]
