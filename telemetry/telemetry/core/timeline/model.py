# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
'''A container for timeline-based events and traces and can handle importing
raw event data from different sources. This model closely resembles that in the
trace_viewer project:
https://code.google.com/p/trace-viewer/
'''

# Register importers for data
from telemetry.core.timeline import inspector_importer
from telemetry.core.timeline.tracing import trace_event_importer
_IMPORTERS = [
    inspector_importer.InspectorTimelineImporter,
    trace_event_importer.TraceEventTimelineImporter
]

class TimelineModel(object):
  def __init__(self, event_data=None, shift_world_to_zero=True):
    self._root_events = []
    self._all_events = []
    self._frozen = False
    self.import_errors = []
    self.metadata = []
    self._bounds = None

    if event_data is not None:
      self.ImportTraces([event_data], shift_world_to_zero=shift_world_to_zero)

  @property
  def min_timestamp(self):
    if self._bounds is None:
      self.UpdateBounds()
    return self._bounds[0]

  @property
  def max_timestamp(self):
    if self._bounds is None:
      self.UpdateBounds()
    return self._bounds[1]

  def AddEvent(self, event):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")
    self._root_events.append(event)
    self._all_events.extend(
      event.GetAllChildrenRecursive(include_self=True))

  def DidFinishRecording(self):
    self._frozen = True

  def ImportTraces(self, traces, shift_world_to_zero=True):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")

    importers = []
    for event_data in traces:
      importers.append(self._CreateImporter(event_data))

    importers.sort(cmp=lambda x, y: x.import_priority - y.import_priority)

    for importer in importers:
      # TODO: catch exceptions here and add it to error list
      importer.ImportEvents()

    for importer in importers:
      importer.FinalizeImport()

    if shift_world_to_zero:
      self.ShiftWorldToZero()

    # Because of FinalizeImport, it would probably be a good idea
    # to prevent the timeline from from being modified.
    self.DidFinishRecording()

  def ShiftWorldToZero(self):
    if not len(self._root_events):
      return
    self.UpdateBounds()
    delta = min(self._root_events, key=lambda e: e.start).start
    for event in self._root_events:
      event.ShiftTimestampsForward(-delta)

  def UpdateBounds(self):
    if not len(self._root_events):
      self._bounds = (0, 0)
      return

    for e in self._root_events:
      e.UpdateBounds()

    first_event = min(self._root_events, key=lambda e: e.start)
    last_event = max(self._root_events, key=lambda e: e.end)
    self._bounds = (first_event.start, last_event.end)

  def GetRootEvents(self):
    return self._root_events

  def GetAllEvents(self):
    return self._all_events

  def GetAllEventsOfName(self, name):
    return [e for e in self._all_events if e.name == name]

  def _CreateImporter(self, event_data):
    for importer_class in _IMPORTERS:
      if importer_class.CanImport(event_data):
        return importer_class(self, event_data)
    raise ValueError("Could not find an importer for the provided event data")
