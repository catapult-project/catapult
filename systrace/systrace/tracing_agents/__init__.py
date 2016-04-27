#!/usr/bin/env python

# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Tracing agent interface for systrace.

This class represents an agent that captures traces from a particular
tool (e.g. atrace, ftrace.)
'''

# Timeout interval constants.

START_STOP_TIMEOUT = 10.0
GET_RESULTS_TIMEOUT = 30.0


class TraceResult(object):
  def __init__(self, source_name, raw_data):
    self.source_name = source_name
    self.raw_data = raw_data


class TracingAgent(object):
  def __init__(self):
    pass

  def StartAgentTracing(self, options, categories, timeout=None):
    '''Starts running the trace for this agent. Stops with timeout if
    not completed within timeout interval.

    Args:
        options: Tracing options.
        categories: Categories of trace events to record.
        timeout: Timeout interval in seconds.

    Returns:
        Boolean value indicating whether or not the trace started successfully.
    '''
    pass

  def StopAgentTracing(self, timeout=None):
    '''Stops running the trace for this agent and returns immediately.
    Stops with timeout if not completed within timeout interval.

    Args:
        timeout: Timeout interval in seconds.

    Returns:
        Boolean value indicating whether or not the trace started successfully.
    '''
    pass

  def SupportsExplicitClockSync(self):
    '''Find out if this agent supports recording of clock sync markers.

    Returns:
        Boolean value indicating whether this agent supports recording
        of clock sync markers.
    '''
    raise NotImplementedError

  def RecordClockSyncMarker(self, sync_id, did_record_sync_marker_callback):
    '''Record a clock sync marker for this agent.

    Args:
        sync_id: Clock sync ID string.
        did_record_sync_marker_callback: Callback function to call
        (with arguments: timestamp and sync_id) after the
        clock sync marker is recorded.
    '''
    raise NotImplementedError

  def GetResults(self, timeout=None):
    '''Get the completed trace for this agent, stopping with timeout

    Get the completed trace for this agent. Call only after
    StopAgentTracing is done. This function blocks until the result
    is collected (note; this may take several seconds). Stops with timeout
    if not completed within self._options.collection_timeout seconds.

    Args:
        timeout: Timeout interval in seconds.
    Returns:
        Completed trace for this agent.
    '''
    pass
