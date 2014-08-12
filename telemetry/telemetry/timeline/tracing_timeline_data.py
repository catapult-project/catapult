# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.timeline.timeline_data import TimelineData


class TracingTimelineData(TimelineData):
  def __init__(self, event_data):
    super(TracingTimelineData, self).__init__()
    self._event_data = event_data

  def Serialize(self, f):
    """Serializes the trace result to a file-like object"""
    if 'traceEvents' in self._event_data:
      json.dump(self._event_data, f, indent=4)
    else:
      json.dump({'traceEvents' : self._event_data}, f, indent=4)

  def EventData(self):
    return self._event_data
