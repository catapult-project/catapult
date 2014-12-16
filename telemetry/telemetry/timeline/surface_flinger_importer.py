# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.timeline import importer
from telemetry.timeline import surface_flinger_timeline_data

class SurfaceFlingerTimelineImporter(importer.TimelineImporter):
  def __init__(self, model, timeline_data):
    super(SurfaceFlingerTimelineImporter, self).__init__(
        model, timeline_data, import_priority=2)
    self._events = timeline_data.EventData()
    self._surface_flinger_process = None

  @staticmethod
  def CanImport(timeline_data):
    if isinstance(timeline_data,
                  surface_flinger_timeline_data.SurfaceFlingerTimelineData):
      return True

    return False

  def ImportEvents(self):
    for event in self._events:
      self._surface_flinger_process = self._model.GetOrCreateProcess(
          event['pid'])
      self._surface_flinger_process.name = 'SurfaceFlinger'
      thread = self._surface_flinger_process.GetOrCreateThread(event['tid'])
      thread.BeginSlice(event['cat'],
                        event['name'],
                        event['ts'],
                        args=event.get('args'))
      thread.EndSlice(event['ts'])

  def FinalizeImport(self):
    '''Called by the Model after all other importers have imported their
    events.'''
    self._model.UpdateBounds()
    self._model.surface_flinger_process = self._surface_flinger_process
