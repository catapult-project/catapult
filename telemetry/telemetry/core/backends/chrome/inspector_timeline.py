# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core.timeline import model


class TabBackendException(Exception):
  """An exception which indicates an error response from devtools inspector."""
  pass


class InspectorTimeline(object):
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
    self._inspector_backend = inspector_backend
    self._is_recording = False
    self._timeline_model = None

  @property
  def timeline_model(self):
    return self._timeline_model

  def Start(self):
    """Starts recording."""
    assert not self._is_recording, 'Start should only be called once.'
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
    """Stops recording and makes a TimelineModel with the event data."""
    assert self._is_recording, 'Stop should be called after Start.'
    request = {'method': 'Timeline.stop'}
    result = self._SendSyncRequest(request)
    raw_events = result['events']
    self._timeline_model = model.TimelineModel(
        event_data=raw_events, shift_world_to_zero=False)
    self._inspector_backend.UnregisterDomain('Timeline')
    self._is_recording = False

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
    # there will be no timeline notifications while recording.
    pass

  def _OnClose(self):
    """Handler called when a domain is unregistered."""
    pass

