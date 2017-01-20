# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import os
import tempfile
import zipfile

class NonSerializableTraceData(Exception):
  """Raised when raw trace data cannot be serialized to TraceData."""
  pass


class TraceDataPart(object):
  """TraceData can have a variety of events.

  These are called "parts" and are accessed by the following fixed field names.
  """
  def __init__(self, raw_field_name):
    self._raw_field_name = raw_field_name

  def __repr__(self):
    return 'TraceDataPart("%s")' % self._raw_field_name

  @property
  def raw_field_name(self):
    return self._raw_field_name

  def __eq__(self, other):
    return self.raw_field_name == other.raw_field_name

  def __hash__(self):
    return hash(self.raw_field_name)


ATRACE_PART = TraceDataPart('systemTraceEvents')
BATTOR_TRACE_PART = TraceDataPart('powerTraceAsString')
CHROME_TRACE_PART = TraceDataPart('traceEvents')
CPU_TRACE_DATA = TraceDataPart('cpuSnapshots')
INSPECTOR_TRACE_PART = TraceDataPart('inspectorTimelineEvents')
SURFACE_FLINGER_PART = TraceDataPart('surfaceFlinger')
TAB_ID_PART = TraceDataPart('tabIds')
TELEMETRY_PART = TraceDataPart('telemetry')

ALL_TRACE_PARTS = {ATRACE_PART,
                   BATTOR_TRACE_PART,
                   CHROME_TRACE_PART,
                   CPU_TRACE_DATA,
                   INSPECTOR_TRACE_PART,
                   SURFACE_FLINGER_PART,
                   TAB_ID_PART,
                   TELEMETRY_PART}

ALL_TRACE_PARTS_RAW_NAMES = set(k.raw_field_name for k in ALL_TRACE_PARTS)

def _HasTraceFor(part, raw):
  assert isinstance(part, TraceDataPart)
  if part.raw_field_name not in raw:
    return False
  return len(raw[part.raw_field_name]) > 0


class TraceData(object):
  """ TraceData holds a collection of traces from multiple sources.

  A TraceData can have multiple active parts. Each part represents traces
  collected from a different trace agent.
  """
  def __init__(self):
    """Creates TraceData from the given data."""
    self._raw_data = {}
    self._events_are_safely_mutable = False

  def _SetFromBuilder(self, d):
    self._raw_data = d
    self._events_are_safely_mutable = True

  @property
  def events_are_safely_mutable(self):
    """Returns true if the events in this value are completely sealed.

    Some importers want to take complex fields out of the TraceData and add
    them to the model, changing them subtly as they do so. If the TraceData
    was constructed with data that is shared with something outside the trace
    data, for instance a test harness, then this mutation is unexpected. But,
    if the values are sealed, then mutating the events is a lot faster.

    We know if events are sealed if the value came from a string, or if the
    value came from a TraceDataBuilder.
    """
    return self._events_are_safely_mutable

  @property
  def active_parts(self):
    return {p for p in ALL_TRACE_PARTS if p.raw_field_name in self._raw_data}

  def HasTracesFor(self, part):
    return _HasTraceFor(part, self._raw_data)

  def GetTracesFor(self, part):
    if not self.HasTracesFor(part):
      return []
    assert isinstance(part, TraceDataPart)
    return self._raw_data[part.raw_field_name]

  def GetTraceFor(self, part):
    assert isinstance(part, TraceDataPart)
    traces = self._raw_data[part.raw_field_name]
    assert len(traces) == 1
    return traces[0]

  # TODO(nedn): unifying this code with
  # telemetry.value.trace.TraceValue._GetTempFileHandle so that we have one
  # single space efficient method to Serialize this to trace.
  def Serialize(self, f, gzip_result=False):
    """Serializes the trace result to a file-like object.

    Write in trace container format if gzip_result=False.
    Writes to a .zip file if gzip_result=True.
    """
    raw_data = {}
    for k, v in self._raw_data.iteritems():
      for data in v:
        if isinstance(data, TraceFileHandle):
          with open(data.file_path) as trace_file:
            trace = json.load(trace_file)
        else:
          trace = data
        if k not in raw_data:
          raw_data[k] = trace
        else:
          raw_data[k] += trace
    if gzip_result:
      zip_file = zipfile.ZipFile(f, mode='w')
      try:
        for part in self.active_parts:
          tmp_file_name = None
          with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file_name = tmp_file.name
            tmp_file.write(str(raw_data[part.raw_field_name]))
          zip_file.write(tmp_file_name, arcname=part.raw_field_name)
          os.remove(tmp_file_name)
      finally:
        zip_file.close()
    else:
      json.dump(raw_data, f)


class TraceFileHandle(object):
  """A trace file handle object allows storing trace data on disk.

  TraceFileHandle API allows one to collect traces from Chrome into disk instead
  of keeping them in memory. This is important for keeping memory usage of
  Telemetry low to avoid OOM (see:
  https://github.com/catapult-project/catapult/issues/3119).

  The fact that this uses a file underneath to store tracing data means the
  callsite is repsonsible for discarding the file when they no longer need the
  tracing data. Call TraceFileHandle.Clean when you done using this object.
  """
  def __init__(self):
    self._backing_file = None
    self._file_path = None

  def Open(self):
    assert not self._backing_file and not self._file_path
    self._backing_file = tempfile.NamedTemporaryFile(delete=False, mode='a')

  def AppendTraceData(self, partial_trace_data):
    assert isinstance(partial_trace_data, basestring)
    self._backing_file.write(partial_trace_data)

  @property
  def file_path(self):
    assert self._file_path, (
        'Either the handle need to be closed first or this handle is cleaned')
    return self._file_path

  def Close(self):
    assert self._backing_file
    self._backing_file.close()
    self._file_path = self._backing_file.name
    self._backing_file = None

  def Clean(self):
    """Remove the backing file used for storing trace on disk.

    This should be called when and only when you no longer need to use
    TraceFileHandle.
    """
    os.remove(self._file_path)
    self._file_path = None


class TraceDataBuilder(object):
  """TraceDataBuilder helps build up a trace from multiple trace agents.

  TraceData is supposed to be immutable, but it is useful during recording to
  have a mutable version. That is TraceDataBuilder.
  """
  def __init__(self):
    self._raw_data = {}

  def AsData(self):
    if self._raw_data == None:
      raise Exception('Can only AsData once')
    data = TraceData()
    data._SetFromBuilder(self._raw_data)
    self._raw_data = None
    return data

  def AddTraceFor(self, part, trace):
    assert isinstance(part, TraceDataPart)
    if part == CHROME_TRACE_PART:
      assert (isinstance(trace, dict) or
              isinstance(trace, TraceFileHandle))
    else:
      assert (isinstance(trace, basestring) or
              isinstance(trace, dict) or
              isinstance(trace, list))

    if self._raw_data == None:
      raise Exception('Already called AsData() on this builder.')

    self._raw_data.setdefault(part.raw_field_name, [])
    self._raw_data[part.raw_field_name].append(trace)

  def HasTracesFor(self, part):
    return _HasTraceFor(part, self._raw_data)


def CreateTraceDataFromRawData(raw_data):
  """Convenient method for creating a TraceData object from |raw_data|.
     This is mostly used for testing.

     Args:
        raw_data can be:
            + A dictionary that repsents multiple trace parts. Keys of the
            dictionary must always contain 'traceEvents', as chrome trace
            must always present.
            + A list that represents Chrome trace events.
            + JSON string of either above.

  """
  raw_data = copy.deepcopy(raw_data)
  if isinstance(raw_data, basestring):
    json_data = json.loads(raw_data)
  else:
    json_data = raw_data

  b = TraceDataBuilder()
  if not json_data:
    return b.AsData()
  if isinstance(json_data, dict):
    assert 'traceEvents' in json_data, 'Only raw chrome trace is supported'
    trace_parts_keys = []
    for k in json_data:
      if k != 'traceEvents' and k in ALL_TRACE_PARTS_RAW_NAMES:
        trace_parts_keys.append(k)
        b.AddTraceFor(TraceDataPart(k), json_data[k])
    # Delete the data for extra keys to form trace data for Chrome part only.
    for k in trace_parts_keys:
      del json_data[k]
    b.AddTraceFor(CHROME_TRACE_PART, json_data)
  elif isinstance(json_data, list):
    b.AddTraceFor(CHROME_TRACE_PART, {'traceEvents': json_data})
  else:
    raise NonSerializableTraceData('Unrecognized data format.')
  return b.AsData()
