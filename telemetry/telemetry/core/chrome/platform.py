# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Platform(object):
  """The platform that the target browser is running on.

  Provides a limited interface to interact with the platform itself, where
  possible. It's important to note that platforms may not provide a specific
  API, so check with IsFooBar() for availability.
  """
  def __init__(self, platform_backend):
    self._platform_backend = platform_backend

  def IsRawDisplayFrameRateSupported(self):
    """Platforms may be able to collect GL surface stats."""
    return self._platform_backend.IsRawDisplayFrameRateSupported()

  def StartRawDisplayFrameRateMeasurement(self, trace_tag):
    """Start measuring GL surface stats."""
    return self._platform_backend.StartRawDisplayFrameRateMeasurement(trace_tag)

  def StopRawDisplayFrameRateMeasurement(self):
    """Stop measuring GL surface stats and print results."""
    return self._platform_backend.StopRawDisplayFrameRateMeasurement()

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


def EmptyPlatform():
  class EmptyPlatformBackend(object):
    def IsRawDisplayFrameRateSupported(self):
      return False

    def StartRawDisplayFrameRateMeasurement(self, _):
      return NotImplementedError()

    def StopRawDisplayFrameRateMeasurement(self):
      return NotImplementedError()

    def SetFullPerformanceModeEnabled(self, enabled):
      pass

    def CanMonitorThermalThrottling(self):
      return False

    def IsThermallyThrottled(self):
      return NotImplementedError()

    def HasBeenThermallyThrottled(self):
      return NotImplementedError()

  return Platform(EmptyPlatformBackend())
