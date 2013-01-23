# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.timeline_event import TimelineEvent
from telemetry.timeline_model import TimelineModel

class TabBackendException(Exception):
  pass

class InspectorTimeline(object):
  """Implementation of dev tools timeline."""
  class Recorder(object):
    """Utility class to Start / Stop recording timeline."""
    def __init__(self, tab):
      self._tab = tab

    def __enter__(self):
      self._tab.StartTimelineRecording()

    def __exit__(self, *args):
      self._tab.StopTimelineRecording()

  def __init__(self, tab_backend):
    self._tab_backend = tab_backend
    self._is_recording = False
    self._timeline_model = None

  @property
  def timeline_model(self):
    return self._timeline_model

  def Start(self):
    if self._is_recording:
      return
    self._is_recording = True
    self._timeline_model = TimelineModel()
    self._tab_backend.RegisterDomain('Timeline',
       self._OnNotification, self._OnClose)
    req = {'method': 'Timeline.start'}
    self._SendSyncRequest(req)

  def Stop(self):
    if not self._is_recording:
      raise TabBackendException('Stop() called but not started')
    self._is_recording = False
    self._timeline_model.DidFinishRecording()
    req = {'method': 'Timeline.stop'}
    self._SendSyncRequest(req)
    self._tab_backend.UnregisterDomain('Timeline')

  def _SendSyncRequest(self, req, timeout=60):
    res = self._tab_backend.SyncRequest(req, timeout)
    if 'error' in res:
      raise TabBackendException(res['error']['message'])
    return res['result']

  def _OnNotification(self, msg):
    if not self._is_recording:
      return
    if 'method' in msg and msg['method'] == 'Timeline.eventRecorded':
      self._OnEventRecorded(msg)

  def _OnEventRecorded(self, msg):
    record = msg.get('params', {}).get('record')
    if record:
      newly_created_event = InspectorTimeline.RawEventToTimelineEvent(record)
      if newly_created_event:
        self._timeline_model.AddEvent(newly_created_event)

  @staticmethod
  def RawEventToTimelineEvent(raw_inspector_event):
    """Converts raw_inspector_event to TimelineEvent."""
    return InspectorTimeline._RawEventToTimelineEventRecursive(
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
      newly_created_event = TimelineEvent(
        name=raw_inspector_event['type'],
        start_time_ms=raw_inspector_event['startTime'],
        duration_ms=(raw_inspector_event['endTime'] -
                     raw_inspector_event['startTime']),
        args=args)
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
      InspectorTimeline._RawEventToTimelineEventRecursive(
        parent_for_children, child)
    return newly_created_event

  def _OnClose(self):
    pass
