# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

# pylint: disable=W0613

class PlatformBackend(object):
  def IsRawDisplayFrameRateSupported(self):
    return False

  def StartRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def StopRawDisplayFrameRateMeasurement(self):
    raise NotImplementedError()

  def GetRawDisplayFrameRateMeasurements(self):
    raise NotImplementedError()

  def SetFullPerformanceModeEnabled(self, enabled):
    pass

  def CanMonitorThermalThrottling(self):
    return False

  def IsThermallyThrottled(self):
    raise NotImplementedError()

  def HasBeenThermallyThrottled(self):
    raise NotImplementedError()

  def GetSystemCommitCharge(self):
    raise NotImplementedError()

  def GetCpuStats(self, pid):
    return {}

  def GetCpuTimestamp(self):
    return {}

  def PurgeUnpinnedMemory(self):
    pass

  def GetMemoryStats(self, pid):
    return {}

  def GetIOStats(self, pid):
    return {}

  def GetChildPids(self, pid):
    raise NotImplementedError()

  def GetCommandLine(self, pid):
    raise NotImplementedError()

  def GetOSName(self):
    raise NotImplementedError()

  def GetOSVersionName(self):
    return None

  def CanFlushIndividualFilesFromSystemCache(self):
    raise NotImplementedError()

  def FlushEntireSystemCache(self):
    raise NotImplementedError()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def LaunchApplication(self, application, parameters=None):
    raise NotImplementedError()

  def IsApplicationRunning(self, application):
    raise NotImplementedError()

  def CanLaunchApplication(self, application):
    return False

  def InstallApplication(self, application):
    raise NotImplementedError()

  def CanCaptureVideo(self):
    return False

  def StartVideoCapture(self, min_bitrate_mbps):
    raise NotImplementedError()

  def StopVideoCapture(self):
    raise NotImplementedError()

  def CanMonitorPowerSync(self):
    return self.CanMonitorPowerAsync()

  def MonitorPowerSync(self, duration_ms):
    self.StartMonitoringPowerAsync()
    time.sleep(duration_ms / 1000.)
    return self.StopMonitoringPowerAsync()

  def CanMonitorPowerAsync(self):
    return False

  def StartMonitoringPowerAsync(self):
    raise NotImplementedError()

  def StopMonitoringPowerAsync(self):
    raise NotImplementedError()
