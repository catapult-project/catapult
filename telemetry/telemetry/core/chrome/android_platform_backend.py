# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys

# Get build/android scripts into our path.
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     '../../../build/android')))

from pylib import perf_tests_helper  # pylint: disable=F0401
from pylib import thermal_throttle  # pylint: disable=F0401

try:
  from pylib import surface_stats_collector # pylint: disable=F0401
except Exception:
  surface_stats_collector = None


class AndroidPlatformBackend(object):
  def __init__(self, adb, window_package, window_activity, no_performance_mode):
    super(AndroidPlatformBackend, self).__init__()
    self._adb = adb
    self._window_package = window_package
    self._window_activity = window_activity
    self._surface_stats_collector = None
    self._perf_tests_setup = perf_tests_helper.PerfTestSetup(self._adb)
    self._thermal_throttle = thermal_throttle.ThermalThrottle(self._adb)
    self._no_performance_mode = no_performance_mode
    if self._no_performance_mode:
      logging.warning('CPU governor will not be set!')

  def IsRawDisplayFrameRateSupported(self):
    return True

  def StartRawDisplayFrameRateMeasurement(self, trace_tag):
    assert not self._surface_stats_collector
    self._surface_stats_collector = \
        surface_stats_collector.SurfaceStatsCollector(
            self._adb, self._window_package, self._window_activity, trace_tag)
    self._surface_stats_collector.__enter__()

  def StopRawDisplayFrameRateMeasurement(self):
    self._surface_stats_collector.__exit__()
    self._surface_stats_collector = None

  def SetFullPerformanceModeEnabled(self, enabled):
    if self._no_performance_mode:
      return
    if enabled:
      self._perf_tests_setup.SetUp()
    else:
      self._perf_tests_setup.TearDown()

  def CanMonitorThermalThrottling(self):
    return True

  def IsThermallyThrottled(self):
    return self._thermal_throttle.IsThrottled()

  def HasBeenThermallyThrottled(self):
    return self._thermal_throttle.HasBeenThrottled()
