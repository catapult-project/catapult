# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import weakref

from telemetry.core.platform import tracing_controller_backend


# pylint: disable=W0613

# pylint: disable=W0212
class OSVersion(str):
  def __new__(cls, friendly_name, sortable_name, *args, **kwargs):
    version = str.__new__(cls, friendly_name)
    version._sortable_name = sortable_name
    return version

  def __lt__(self, other):
    return self._sortable_name < other._sortable_name

  def __gt__(self, other):
    return self._sortable_name > other._sortable_name

  def __le__(self, other):
    return self._sortable_name <= other._sortable_name

  def __ge__(self, other):
    return self._sortable_name >= other._sortable_name


XP =           OSVersion('xp',            5.1)
VISTA =        OSVersion('vista',         6.0)
WIN7 =         OSVersion('win7',          6.1)
WIN8 =         OSVersion('win8',          6.2)

LEOPARD =      OSVersion('leopard',      10.5)
SNOWLEOPARD =  OSVersion('snowleopard',  10.6)
LION =         OSVersion('lion',         10.7)
MOUNTAINLION = OSVersion('mountainlion', 10.8)
MAVERICKS =    OSVersion('mavericks',    10.9)


class PlatformBackend(object):
  def __init__(self):
    self._platform = None
    self._running_browser_backends = weakref.WeakSet()
    self._tracing_controller_backend = \
        tracing_controller_backend.TracingControllerBackend(self)

  def SetPlatform(self, platform):
    assert self._platform == None
    self._platform = platform

  @property
  def platform(self):
    return self._platform

  @property
  def running_browser_backends(self):
    return list(self._running_browser_backends)

  @property
  def tracing_controller_backend(self):
    return self._tracing_controller_backend

  def DidCreateBrowser(self, browser, browser_backend):
    self.SetFullPerformanceModeEnabled(True)

  def DidStartBrowser(self, browser, browser_backend):
    assert browser not in self._running_browser_backends
    self._running_browser_backends.add(browser_backend)
    self._tracing_controller_backend.DidStartBrowser(
        browser, browser_backend)

  def WillCloseBrowser(self, browser, browser_backend):
    self._tracing_controller_backend.WillCloseBrowser(
        browser, browser_backend)

    is_last_browser = len(self._running_browser_backends) == 1
    if is_last_browser:
      self.SetFullPerformanceModeEnabled(False)

    self._running_browser_backends.remove(browser_backend)

  def GetBackendForBrowser(self, browser):
    matches = [x for x in self._running_browser_backends
               if x.browser == browser]
    if len(matches) == 0:
      raise Exception('No browser found')
    assert len(matches) == 1
    return matches[0]

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

  def GetSystemTotalPhysicalMemory(self):
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
    raise NotImplementedError()

  def CanFlushIndividualFilesFromSystemCache(self):
    raise NotImplementedError()

  def FlushEntireSystemCache(self):
    raise NotImplementedError()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    raise NotImplementedError()

  def FlushDnsCache(self):
    pass

  def LaunchApplication(
      self, application, parameters=None, elevate_privilege=False):
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

  @property
  def is_video_capture_running(self):
    return False

  def StopVideoCapture(self):
    raise NotImplementedError()

  def CanMonitorPower(self):
    return False

  def CanMeasurePerApplicationPower(self):
    return False

  def StartMonitoringPower(self, browser):
    raise NotImplementedError()

  def StopMonitoringPower(self):
    raise NotImplementedError()
