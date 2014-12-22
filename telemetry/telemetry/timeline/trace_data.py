# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import numbers

class NonSerializableTraceData(Exception):
  """Raised when raw trace data cannot be serialized to TraceData."""
  pass


def _ValidateRawData(raw):
  try:
    json.dumps(raw)
  except TypeError as e:
    raise NonSerializableTraceData('TraceData is not serilizable: %s' % e)
  except ValueError as e:
    raise NonSerializableTraceData('TraceData is not serilizable: %s' % e)


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


CHROME_TRACE_PART = TraceDataPart('traceEvents')
INSPECTOR_TRACE_PART = TraceDataPart('inspectorTimelineEvents')
SURFACE_FLINGER_PART = TraceDataPart('surfaceFlinger')
TAB_ID_PART = TraceDataPart('tabIds')

ALL_TRACE_PARTS = {CHROME_TRACE_PART,
                   INSPECTOR_TRACE_PART,
                   SURFACE_FLINGER_PART,
                   TAB_ID_PART}


def _HasEventsFor(part, raw):
  assert isinstance(part, TraceDataPart)
  if part.raw_field_name not in raw:
    return False
  return len(raw[part.raw_field_name]) > 0


class TraceData(object):
  """Validates, parses, and serializes raw data.

  NOTE: raw data must only include primitive objects!
  By design, TraceData must contain only data that is BOTH json-serializable
  to a file, AND restorable once again from that file into TraceData without
  assistance from other classes.

  Raw data can be one of three standard trace_event formats:
  1. Trace container format: a json-parseable dict.
  2. A json-parseable array: assumed to be chrome trace data.
  3. A json-parseable array missing the final ']': assumed to be chrome trace
     data.
  """
  def __init__(self, raw_data=None):
    """Creates TraceData from the given data."""
    self._raw_data = {}
    self._events_are_safely_mutable = False
    if not raw_data:
      return
    _ValidateRawData(raw_data)

    if isinstance(raw_data, basestring):
      if raw_data.startswith('[') and not raw_data.endswith(']'):
        if raw_data.endswith(','):
          raw_data = raw_data[:-1]
        raw_data += ']'
      json_data = json.loads(raw_data)
      # The parsed data isn't shared with anyone else, so we mark this value
      # as safely mutable.
      self._events_are_safely_mutable = True
    else:
      json_data = raw_data

    if isinstance(json_data, dict):
      self._raw_data = json_data
    elif isinstance(json_data, list):
      if len(json_data) == 0:
        self._raw_data = {}
      self._raw_data = {CHROME_TRACE_PART.raw_field_name: json_data}
    else:
      raise Exception('Unrecognized data format.')

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

  @property
  def metadata_records(self):
    part_field_names = {p.raw_field_name for p in ALL_TRACE_PARTS}
    for k, v in self._raw_data.iteritems():
      if k in part_field_names:
        continue
      yield {
        'name': k,
        'value': self._raw_data[v]
      }

  def HasEventsFor(self, part):
    return _HasEventsFor(part, self._raw_data)

  def GetEventsFor(self, part):
    if not self.HasEventsFor(part):
      return []
    assert isinstance(part, TraceDataPart)
    return self._raw_data[part.raw_field_name]

  def Serialize(self, f, gzip_result=False):
    """Serializes the trace result to a file-like object.

    Always writes in the trace container format.
    """
    assert not gzip_result, 'Not implemented'
    json.dump(self._raw_data, f)


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

  def AddEventsTo(self, part, events):
    """Note: this won't work when called from multiple browsers.

    Each browser's trace_event_impl zeros its timestamps when it writes them
    out and doesn't write a timebase that can be used to re-sync them.
    """
    assert isinstance(part, TraceDataPart)
    assert isinstance(events, list)
    if self._raw_data == None:
      raise Exception('Already called AsData() on this builder.')

    self._raw_data.setdefault(part.raw_field_name, []).extend(events)

  def HasEventsFor(self, part):
    return _HasEventsFor(part, self._raw_data)
