# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.platform import linux_platform_backend


class CrosPlatformBackend(linux_platform_backend.LinuxPlatformBackend):

  def __init__(self, cri):
    super(CrosPlatformBackend, self).__init__()
    self._cri = cri

  def StartRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def GetRawDisplayFrameRateMeasurements(self):
    raise NotImplementedError()

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def _RunCommand(self, args):
    return self._cri.RunCmdOnDevice(args)[0]

  def _GetFileContents(self, filename):
    try:
      return self._cri.RunCmdOnDevice(['cat', filename])[0]
    except AssertionError:
      return ''

  def GetOSName(self):
    return 'chromeos'
