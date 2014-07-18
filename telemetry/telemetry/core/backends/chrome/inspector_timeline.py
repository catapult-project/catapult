# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.backends.chrome import timeline_recorder
from telemetry.timeline import inspector_timeline_data


class TabBackendException(Exception):
  """An exception which indicates an error response from devtools inspector."""
  pass


class InspectorTimeline(timeline_recorder.TimelineRecorder):
  """Implementation of dev tools timeline."""

  class Recorder(object):
    """Utility class to Start and Stop recording timeline.

    Example usage:

        with inspector_timeline.InspectorTimeline.Recorder(tab):
          # Something to run while the timeline is recording.

    This is an alternative to directly calling the Start and Stop methods below.
    """
    def __init__(self, tab):
      self._tab = tab

    def __enter__(self):
      self._tab.StartTimelineRecording()

    def __exit__(self, *args):
      self._tab.StopTimelineRecording()

  def __init__(self, inspector_backend):
    super(InspectorTimeline, self).__init__()
    self._inspector_backend = inspector_backend
    self._is_recording = False
    self._raw_events = None

  @property
  def is_timeline_recording_running(self):
    return self._is_recording

  def Start(self):
    """Starts recording."""
    assert not self._is_recording, 'Start should only be called once.'
    self._raw_events = None
    self._is_recording = True
    self._inspector_backend.RegisterDomain(
        'Timeline', self._OnNotification, self._OnClose)
    # The 'bufferEvents' parameter below means that events should not be sent
    # individually as messages, but instead all at once when a Timeline.stop
    # request is sent.
    request = {
        'method': 'Timeline.start',
        'params': {'bufferEvents': True},
    }
    self._SendSyncRequest(request)

  def Stop(self):
    """Stops recording and returns timeline event data."""
    if not self._is_recording:
      return None
    request = {'method': 'Timeline.stop'}
    result = self._SendSyncRequest(request)
    self._inspector_backend.UnregisterDomain('Timeline')
    self._is_recording = False

    # TODO: Backward compatibility. Needs to be removed when
    # M38 becomes stable.
    if 'events' in result:
      raw_events = result['events']
    else:  # In M38 events will arrive via Timeline.stopped event.
      raw_events = self._raw_events
      self._raw_events = None
    return inspector_timeline_data.InspectorTimelineData(raw_events)

  def _SendSyncRequest(self, request, timeout=60):
    """Sends a devtools remote debugging protocol request.

    The types of request that are valid is determined by protocol.json:
    https://src.chromium.org/viewvc/blink/trunk/Source/devtools/protocol.json

    Args:
      request: Request dict, may contain the keys 'method' and 'params'.
      timeout: Number of seconds to wait for a response.

    Returns:
      The result given in the response message.

    Raises:
      TabBackendException: The response indicates an error occurred.
    """
    response = self._inspector_backend.SyncRequest(request, timeout)
    if 'error' in response:
      raise TabBackendException(response['error']['message'])
    return response['result']

  def _OnNotification(self, msg):
    """Handler called when a message is received."""
    # Since 'Timeline.start' was invoked with the 'bufferEvents' parameter,
    # the events will arrive in Timeline.stopped event.
    if msg['method'] == 'Timeline.stopped' and 'events' in msg['params']:
      self._raw_events = msg['params']['events']

  def _OnClose(self):
    """Handler called when a domain is unregistered."""
    pass
