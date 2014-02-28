# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import weakref

from telemetry.core.timeline_data import TimelineData

class TracingTimelineData(TimelineData):
  def __init__(self, event_data, tab_to_marker_mapping = None):
    super(TracingTimelineData, self).__init__()
    self._event_data = event_data
    if tab_to_marker_mapping == None:
      self._tab_to_marker_mapping = weakref.WeakKeyDictionary()
    else:
      self._tab_to_marker_mapping = tab_to_marker_mapping

  def Serialize(self, f):
    """Serializes the trace result to a file-like object"""
    f.write('{"traceEvents":')
    json.dump(self._event_data, f)
    f.write('}')

  def EventData(self):
    return self._event_data

  def AugmentTimelineModel(self, timeline):
    for thread in timeline.GetAllThreads():
      if thread.name == 'CrBrowserMain':
        timeline.browser_process = thread.parent
    for key, value in self._tab_to_marker_mapping.iteritems():
      timeline_markers = timeline.FindTimelineMarkers(value)
      assert(len(timeline_markers) == 1)
      renderer_process = timeline_markers[0].start_thread.parent
      timeline.AddCoreObjectToContainerMapping(key, renderer_process)
