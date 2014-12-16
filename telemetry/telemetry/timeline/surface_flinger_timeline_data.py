# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.timeline.timeline_data import TimelineData


class SurfaceFlingerTimelineData(TimelineData):
  def __init__(self, pid, refresh_period, timestamps):
    super(SurfaceFlingerTimelineData, self).__init__()
    self._events = []
    for ts in timestamps:
      self._events.append(
        {'cat': 'SurfaceFlinger',
         'name': 'vsync_before',
         'ts': ts,
         'pid': pid,
         'tid': pid,
         'args': {'data': {'frame_count': 1,
                           'refresh_period': refresh_period}}})

  def Serialize(self, f):
    """Serializes the surface flinger data to a file-like object"""
    json.dump(self._events, f, indent=4)

  def EventData(self):
    return self._events
