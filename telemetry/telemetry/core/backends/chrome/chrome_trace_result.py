# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import weakref


class ChromeTraceResult(object):
  def __init__(self, tracing_data, tab_to_marker_mapping = None):
    self._tracing_data = tracing_data
    if tab_to_marker_mapping == None:
      self._tab_to_marker_mapping = weakref.WeakKeyDictionary()
    else:
      self._tab_to_marker_mapping = tab_to_marker_mapping

  def Serialize(self, f):
    """Serializes the trace result to a file-like object"""
    raise NotImplementedError()

  def AsTimelineModel(self):
    """Parses the trace result into a timeline model for in-memory
    manipulation."""
    timeline = self._CreateTimelineModel()
    for thread in timeline.GetAllThreads():
      if thread.name == 'CrBrowserMain':
        timeline.browser_process = thread.parent
    for key, value in self._tab_to_marker_mapping.iteritems():
      timeline_markers = timeline.FindTimelineMarkers(value)
      assert(len(timeline_markers) == 1)
      renderer_process = timeline_markers[0].start_thread.parent
      timeline.AddCoreObjectToContainerMapping(key, renderer_process)
    return timeline

  def _CreateTimelineModel(self):
    raise NotImplementedError()
