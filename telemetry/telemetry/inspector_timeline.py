# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class InspectorBackendException(Exception):
  pass


class TimelineEvent(object):
  """Represents a timeline event."""
  def __init__(self, d):
    self.__dict__.update(d)

  @property
  def type(self):
    return self.__dict__.get('type')

  @property
  def start_time(self):
    return self.__dict__.get('startTime', 0)

  @property
  def end_time(self):
    return self.__dict__.get('endTime', 0)

  @property
  def elapsed_time(self):
    return self.end_time - self.start_time


class TimelineEvents(object):
  def __init__(self):
    self._events = []

  def AppendRawEvents(self, raw_inspector_stream):
    if raw_inspector_stream.get('params', {}).get('record'):
      self._FlattenEvents(raw_inspector_stream['params']['record'])

  def _FlattenEvents(self, raw_inspector_events):
    self._events.append(TimelineEvent(raw_inspector_events))
    for child in raw_inspector_events.get('children', []):
      self._FlattenEvents(child)

  def GetAllOfType(self, type_name):
    return [e for e in self._events if e.type == type_name]


class InspectorTimeline(object):
  """Implementation of dev tools timeline."""
  class Recorder(object):
    """Utility class to Start / Stop recording timeline."""
    def __init__(self, timeline):
      self._timeline = timeline

    def __enter__(self):
      self._timeline.Start()

    def __exit__(self, *args):
      self._timeline.Stop()

  def __init__(self, inspector_backend, tab):
    self._inspector_backend = inspector_backend
    self._tab = tab
    self._is_recording = False
    self._timeline_events = None

  @property
  def timeline_events(self):
    return self._timeline_events

  def Start(self):
    if self._is_recording:
      return
    self._timeline_events = TimelineEvents()
    self._is_recording = True
    self._inspector_backend.RegisterDomain('Timeline',
       self._OnNotification, self._OnClose)
    req = {'method': 'Timeline.start'}
    self._SendSyncRequest(req)

  def Stop(self):
    if not self._is_recording:
      raise InspectorBackendException('Stop() called but not started')
    self._is_recording = False
    req = {'method': 'Timeline.stop'}
    self._SendSyncRequest(req)
    self._inspector_backend.UnregisterDomain('Timeline')

  def _SendSyncRequest(self, req, timeout=60):
    res = self._inspector_backend.SyncRequest(req, timeout)
    if 'error' in res:
      raise InspectorBackendException(res['error']['message'])
    return res['result']

  def _OnNotification(self, msg):
    if not self._is_recording:
      return
    if 'method' in msg and msg['method'] == 'Timeline.eventRecorded':
      self._timeline_events.AppendRawEvents(msg)

  def _OnClose(self):
    if self._is_recording:
      raise InspectorBackendException('InspectTimeline received OnClose whilst '
          'recording.')
