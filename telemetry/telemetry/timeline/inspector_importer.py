# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
'''Imports event data obtained from the inspector's timeline.'''

from telemetry.timeline import importer
from telemetry.timeline import inspector_timeline_data
import telemetry.timeline.thread as timeline_thread
import telemetry.timeline.slice as tracing_slice

class InspectorTimelineImporter(importer.TimelineImporter):
  def __init__(self, model, timeline_data):
    super(InspectorTimelineImporter, self).__init__(model, timeline_data)

  @staticmethod
  def CanImport(timeline_data):
    ''' Checks if timeline_data is from the inspector timeline. We assume
    that if the first event is a valid inspector event, we can import the
    entire list.
    '''
    if not isinstance(timeline_data,
                      inspector_timeline_data.InspectorTimelineData):
      return False

    event_data = timeline_data.EventData()

    if isinstance(event_data, list) and len(event_data):
      event_datum = event_data[0]
      return 'startTime' in event_datum and 'type' in event_datum
    return False

  def ImportEvents(self):
    render_process = self._model.GetOrCreateProcess(0)
    for raw_event in self._timeline_data.EventData():
      thread = render_process.GetOrCreateThread(raw_event.get('thread', 0))
      InspectorTimelineImporter.AddRawEventToThreadRecursive(thread, raw_event)

  def FinalizeImport(self):
    pass

  @staticmethod
  def AddRawEventToThreadRecursive(thread, raw_inspector_event):
    pending_slice = None
    if ('startTime' in raw_inspector_event and
        'type' in raw_inspector_event):
      args = {}
      for x in raw_inspector_event:
        if x in ('startTime', 'endTime', 'children'):
          continue
        args[x] = raw_inspector_event[x]
      if len(args) == 0:
        args = None
      start_time = raw_inspector_event['startTime']
      end_time = raw_inspector_event.get('endTime', start_time)

      pending_slice = tracing_slice.Slice(
        thread, 'inspector',
        raw_inspector_event['type'],
        start_time,
        thread_timestamp=None,
        args=args)

    for child in raw_inspector_event.get('children', []):
      InspectorTimelineImporter.AddRawEventToThreadRecursive(
          thread, child)

    if pending_slice:
      pending_slice.duration = end_time - pending_slice.start
      thread.PushSlice(pending_slice)

  @staticmethod
  def RawEventToTimelineEvent(raw_inspector_event):
    """Converts raw_inspector_event to TimelineEvent."""
    thread = timeline_thread.Thread(None, 0)
    InspectorTimelineImporter.AddRawEventToThreadRecursive(
        thread, raw_inspector_event)
    thread.FinalizeImport()
    assert len(thread.toplevel_slices) <= 1
    if len(thread.toplevel_slices) == 0:
      return None
    return thread.toplevel_slices[0]
