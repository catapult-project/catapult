# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions


class PowerMonitor(object):
  """A power profiler.

  Provides an interface to register power consumption during a test.
  """
  def CanMonitorPower(self):
    """Returns True iff power can be monitored asynchronously via
    StartMonitoringPower() and StopMonitoringPower().
    """
    return False

  def CanMeasurePerApplicationPower(self):
    """Returns True if the power monitor can measure power for the target
    application in isolation. False if power measurement is for full system
    energy consumption."""
    return False

  def StartMonitoringPower(self, browser):
    """Starts monitoring power utilization statistics.

    See Platform#StartMonitoringPower for the arguments format.
    """
    raise NotImplementedError()

  def StopMonitoringPower(self):
    """Stops monitoring power utilization and returns collects stats

    See Platform#StopMonitoringPower for the return format.
    """
    raise NotImplementedError()
