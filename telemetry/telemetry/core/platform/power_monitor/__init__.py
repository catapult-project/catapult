# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import exceptions


class PowerMonitor(object):
  """A power profiler.

  Provides an interface to register power consumption during a test.
  """
  def CanMonitorPowerAsync(self):
    """Returns True iff power can be monitored asynchronously via
    StartMonitoringPowerAsync() and StopMonitoringPowerAsync().
    """
    return False

  def StartMonitoringPowerAsync(self):
    """Starts monitoring power utilization statistics."""
    raise NotImplementedError()

  def StopMonitoringPowerAsync(self):
    """Stops monitoring power utilization and returns collects stats

    See Platform#StopMonitoringPowerAsync for the return format.
    """
    raise NotImplementedError()
