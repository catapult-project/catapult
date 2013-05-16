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
_IMPORTERS = [inspector_importer.InspectorTimelineImporter]

class TimelineModel(object):
  def __init__(self):
    self._events = []
    self._frozen = False

  def AddEvent(self, event):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")
    self._events.extend(
      event.GetAllChildrenRecursive(include_self=True))

  def DidFinishRecording(self):
    self._frozen = True

  def ImportTraces(self, traces):
    if self._frozen:
      raise Exception("Cannot add events once recording is done")

    importers = []
    for event_data in traces:
      importers.append(self._CreateImporter(event_data))

    importers.sort(cmp=lambda x, y: x.import_priority - y.import_priority)

    for importer in importers:
      importer.ImportEvents()

    for importer in importers:
      importer.FinalizeImport()

    # Because of FinalizeImport, it would probably be a good idea
    # to prevent the timeline from from being modified.
    self.DidFinishRecording()

  def GetAllEvents(self):
    return self._events

  def GetAllOfName(self, name):
    return [e for e in self._events if e.name == name]

  def _CreateImporter(self, event_data):
    for importer_class in _IMPORTERS:
      if importer_class.CanImport(event_data):
        return importer_class(self, event_data)
    raise ValueError("Could not find an importer for the provided event data")
