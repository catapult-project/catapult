# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

# Get build/android scripts into our path.
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__),
                     '..', '..', '..', 'build', 'android')))
try:
  from pylib import surface_stats_collector # pylint: disable=F0401
except Exception:
  surface_stats_collector = None


class AndroidPlatform(object):
  def __init__(self, adb, window_package, window_activity):
    super(AndroidPlatform, self).__init__()
    self._adb = adb
    self._window_package = window_package
    self._window_activity = window_activity

  def GetSurfaceCollector(self, trace_tag):
    return surface_stats_collector.SurfaceStatsCollector(
        self._adb, self._window_package, self._window_activity, trace_tag)
