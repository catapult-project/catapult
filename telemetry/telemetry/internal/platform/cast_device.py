# Copyright 2022 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A device used for Cast"""

from __future__ import absolute_import
from telemetry.core import cast_interface
from telemetry.internal.platform import device


class CastDevice(device.Device):
  def __init__(self, output_dir, runtime_exe):
    self._output_dir = output_dir
    self._runtime_exe = runtime_exe
    super(CastDevice, self).__init__(name='cast', guid='cast')

  @classmethod
  def GetAllConnectedDevices(cls, denylist):
    return []

  @property
  def output_dir(self):
    return self._output_dir

  @property
  def runtime_exe(self):
    return self._runtime_exe


def FindAllAvailableDevices(options):
  """Returns a list of available devices.
  """
  if options.browser_type not in cast_interface.CAST_BROWSERS:
    return []
  return [CastDevice(options.cast_output_dir, options.cast_runtime_exe)]
