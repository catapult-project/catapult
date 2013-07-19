# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
'''Imports event data obtained from the inspector's timeline.'''

from telemetry.core.timeline import importer
import telemetry.core.timeline.event as timeline_event

class InspectorTimelineImporter(importer.TimelineImporter):
  def __init__(self, model, event_data):
    super(InspectorTimelineImporter, self).__init__(model, event_data)

  @staticmethod
  def CanImport(event_data):
    ''' Checks if event_data is from the inspector timeline. We assume
    that if the first event is a valid inspector event, we can import the
    entire list.
    '''
    if isinstance(event_data, list) and len(event_data):
      event_datum = event_data[0]
      return 'startTime' in event_datum and 'endTime' in event_datum
    return False

  def ImportEvents(self):
    for raw_event in self._event_data:
      event = self.RawEventToTimelineEvent(raw_event)
      if event:
        self._model.AddEvent(event)

  def FinalizeImport(self):
    pass

  @staticmethod
  def RawEventToTimelineEvent(raw_inspector_event):
    """Converts raw_inspector_event to TimelineEvent."""
    return InspectorTimelineImporter._RawEventToTimelineEventRecursive(
      None, raw_inspector_event)

  @staticmethod
  def _RawEventToTimelineEventRecursive(
    parent_for_created_events, raw_inspector_event):
    """
    Creates a new TimelineEvent for the raw_inspector_event, if possible, adding
    it to the provided parent_for_created_events.

    It then recurses on any child events found inside, building a tree of
    TimelineEvents.

    Returns the root of the created tree, or None.
    """
    # Create a TimelineEvent for this raw_inspector_event if possible. Only
    # events with start-time and end-time get imported.
    if ('startTime' in raw_inspector_event and
        'endTime' in raw_inspector_event):
      args = {}
      for x in raw_inspector_event:
        if x in ('startTime', 'endTime', 'children'):
          continue
        args[x] = raw_inspector_event[x]
      if len(args) == 0:
        args = None
      newly_created_event = timeline_event.TimelineEvent(
        name=raw_inspector_event['type'],
        start=raw_inspector_event['startTime'],
        duration=(raw_inspector_event['endTime'] -
                     raw_inspector_event['startTime']),
        args=args,
        parent=parent_for_created_events)
      if parent_for_created_events:
        parent_for_created_events.children.append(newly_created_event)
    else:
      newly_created_event = None

    # Process any children events, creating TimelineEvents for them as well.
    if newly_created_event:
      parent_for_children = newly_created_event
    else:
      parent_for_children = parent_for_created_events
    for child in raw_inspector_event.get('children', []):
      InspectorTimelineImporter._RawEventToTimelineEventRecursive(
        parent_for_children, child)
    return newly_created_event
