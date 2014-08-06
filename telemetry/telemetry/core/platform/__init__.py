# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys


_host_platform = None


def _InitHostPlatformIfNeeded():
  global _host_platform
  if _host_platform:
    return

  if sys.platform.startswith('linux'):
    from telemetry.core.platform import linux_platform_backend
    backend = linux_platform_backend.LinuxPlatformBackend()
  elif sys.platform == 'darwin':
    from telemetry.core.platform import mac_platform_backend
    backend = mac_platform_backend.MacPlatformBackend()
  elif sys.platform == 'win32':
    from telemetry.core.platform import win_platform_backend
    backend = win_platform_backend.WinPlatformBackend()
  else:
    raise NotImplementedError()

  _host_platform = Platform(backend)


def GetHostPlatform():
  _InitHostPlatformIfNeeded()
  return _host_platform


class Platform(object):
  """The platform that the target browser is running on.

  Provides a limited interface to interact with the platform itself, where
  possible. It's important to note that platforms may not provide a specific
  API, so check with IsFooBar() for availability.
  """
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend
    self._platform_backend.SetPlatform(self)

  def IsRawDisplayFrameRateSupported(self):
    """Platforms may be able to collect GL surface stats."""
    return self._platform_backend.IsRawDisplayFrameRateSupported()

  def StartRawDisplayFrameRateMeasurement(self):
    """Start measuring GL surface stats."""
    return self._platform_backend.StartRawDisplayFrameRateMeasurement()

  def StopRawDisplayFrameRateMeasurement(self):
    """Stop measuring GL surface stats."""
    return self._platform_backend.StopRawDisplayFrameRateMeasurement()

  class RawDisplayFrameRateMeasurement(object):
    def __init__(self, name, value, unit):
      self._name = name
      self._value = value
      self._unit = unit

    @property
    def name(self):
      return self._name

    @property
    def value(self):
      return self._value

    @property
    def unit(self):
      return self._unit

  def GetRawDisplayFrameRateMeasurements(self):
    """Returns a list of RawDisplayFrameRateMeasurement."""
    return self._platform_backend.GetRawDisplayFrameRateMeasurements()

  def SetFullPerformanceModeEnabled(self, enabled):
    """Platforms may tweak their CPU governor, system status, etc.

    Most platforms can operate in a battery saving mode. While good for battery
    life, this can cause confusing performance results and add noise. Turning
    full performance mode on disables these features, which is useful for
    performance testing.
    """
    return self._platform_backend.SetFullPerformanceModeEnabled(enabled)

  def CanMonitorThermalThrottling(self):
    """Platforms may be able to detect thermal throttling.

    Some fan-less computers go into a reduced performance mode when their heat
    exceeds a certain threshold. Performance tests in particular should use this
    API to detect if this has happened and interpret results accordingly.
    """
    return self._platform_backend.CanMonitorThermalThrottling()

  def IsThermallyThrottled(self):
    """Returns True if the device is currently thermally throttled."""
    return self._platform_backend.IsThermallyThrottled()

  def HasBeenThermallyThrottled(self):
    """Returns True if the device has been thermally throttled."""
    return self._platform_backend.HasBeenThermallyThrottled()

  def GetOSName(self):
    """Returns a string description of the Platform OS.

    Examples: WIN, MAC, LINUX, CHROMEOS"""
    return self._platform_backend.GetOSName()

  def GetOSVersionName(self):
    """Returns a logically sortable, string-like description of the Platform OS
    version.

    Examples: VISTA, WIN7, LION, MOUNTAINLION"""
    return self._platform_backend.GetOSVersionName()

  def CanFlushIndividualFilesFromSystemCache(self):
    """Returns true if the disk cache can be flushed for specific files."""
    return self._platform_backend.CanFlushIndividualFilesFromSystemCache()

  def FlushEntireSystemCache(self):
    """Flushes the OS's file cache completely.

    This function may require root or administrator access."""
    return self._platform_backend.FlushEntireSystemCache()

  def FlushSystemCacheForDirectory(self, directory, ignoring=None):
    """Flushes the OS's file cache for the specified directory.

    Any files or directories inside |directory| matching a name in the
    |ignoring| list will be skipped.

    This function does not require root or administrator access."""
    return self._platform_backend.FlushSystemCacheForDirectory(
        directory, ignoring=ignoring)

  def FlushDnsCache(self):
    """Flushes the OS's DNS cache completely.

    This function may require root or administrator access."""
    return self._platform_backend.FlushDnsCache()

  def LaunchApplication(self, application, parameters=None,
                        elevate_privilege=False):
    """"Launches the given |application| with a list of |parameters| on the OS.

    Set |elevate_privilege| to launch the application with root or admin rights.

    Returns:
      A popen style process handle for host platforms.
    """
    return self._platform_backend.LaunchApplication(
        application, parameters, elevate_privilege=elevate_privilege)

  def IsApplicationRunning(self, application):
    """Returns whether an application is currently running."""
    return self._platform_backend.IsApplicationRunning(application)

  def CanLaunchApplication(self, application):
    """Returns whether the platform can launch the given application."""
    return self._platform_backend.CanLaunchApplication(application)

  def InstallApplication(self, application):
    """Installs the given application."""
    return self._platform_backend.InstallApplication(application)

  def CanCaptureVideo(self):
    """Returns a bool indicating whether the platform supports video capture."""
    return self._platform_backend.CanCaptureVideo()

  def StartVideoCapture(self, min_bitrate_mbps):
    """Starts capturing video.

    Outer framing may be included (from the OS, browser window, and webcam).

    Args:
      min_bitrate_mbps: The minimum capture bitrate in MegaBits Per Second.
          The platform is free to deliver a higher bitrate if it can do so
          without increasing overhead.

    Raises:
      ValueError if the required |min_bitrate_mbps| can't be achieved.
    """
    return self._platform_backend.StartVideoCapture(min_bitrate_mbps)

  def StopVideoCapture(self):
    """Stops capturing video.

    Returns:
      A telemetry.core.video.Video object.
    """
    return self._platform_backend.StopVideoCapture()

  def CanMonitorPower(self):
    """Returns True iff power can be monitored asynchronously via
    StartMonitoringPower() and StopMonitoringPower().
    """
    return self._platform_backend.CanMonitorPower()

  def CanMeasurePerApplicationPower(self):
    """Returns True if the power monitor can measure power for the target
    application in isolation. False if power measurement is for full system
    energy consumption."""
    return self._platform_backend.CanMeasurePerApplicationPower()


  def StartMonitoringPower(self, browser):
    """Starts monitoring power utilization statistics.

    Args:
      browser: The browser to monitor.
    """
    assert self._platform_backend.CanMonitorPower()
    self._platform_backend.StartMonitoringPower(browser)

  def StopMonitoringPower(self):
    """Stops monitoring power utilization and returns stats

    Returns:
      None if power measurement failed for some reason, otherwise a dict of
      power utilization statistics containing: {
        # An identifier for the data provider. Allows to evaluate the precision
        # of the data. Example values: monsoon, powermetrics, ds2784
        'identifier': identifier,

        # The instantaneous power (voltage * current) reading in milliwatts at
        # each sample.
        'power_samples_mw':  [mw0, mw1, ..., mwN],

        # The full system energy consumption during the sampling period in
        # milliwatt hours. May be estimated by integrating power samples or may
        # be exact on supported hardware.
        'energy_consumption_mwh': mwh,

        # The target application's energy consumption during the sampling period
        # in milliwatt hours. Should be returned iff
        # CanMeasurePerApplicationPower() return true.
        'application_energy_consumption_mwh': mwh,

        # A platform-specific dictionary of additional details about the
        # utilization of individual hardware components.
        component_utilization: {

          # Platform-specific data not attributed to any particular hardware
          # component.
          whole_package: {

            # Device-specific onboard temperature sensor.
            'average_temperature_c': c,

            ...
          }

          ...
        }
      }
    """
    return self._platform_backend.StopMonitoringPower()
