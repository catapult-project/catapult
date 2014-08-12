# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.timeline.timeline_data import TimelineData


class EmptyTimelineDataImporter(object):
  """Imports empty TimlineData objects."""
  def __init__(self, model, timeline_data, import_priority=0):
    pass

  @staticmethod
  def CanImport(timeline_data):
    if not isinstance(timeline_data, TimelineData):
      return False
    event_data = timeline_data.EventData()
    if isinstance(event_data, list):
      return len(event_data) == 0
    elif isinstance(event_data, basestring):
      return len(event_data) == 0
    return False

  def ImportEvents(self):
    pass

  def FinalizeImport(self):
    pass
