# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import copy
import gzip
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time


try:
  StringTypes = basestring
except NameError:
  StringTypes = str


_TRACING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            os.path.pardir, os.path.pardir)
_TRACE2HTML_PATH = os.path.join(_TRACING_DIR, 'bin', 'trace2html')


class NonSerializableTraceData(Exception):
  """Raised when raw trace data cannot be serialized."""
  pass


class TraceDataPart(object):
  """Trace data can come from a variety of tracing agents.

  Data from each agent is collected into a trace "part" and accessed by the
  following fixed field names.
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


ANDROID_PROCESS_DATA_PART = TraceDataPart('androidProcessDump')
ATRACE_PART = TraceDataPart('systemTraceEvents')
ATRACE_PROCESS_DUMP_PART = TraceDataPart('atraceProcessDump')
CHROME_TRACE_PART = TraceDataPart('traceEvents')
CPU_TRACE_DATA = TraceDataPart('cpuSnapshots')
TELEMETRY_PART = TraceDataPart('telemetry')
WALT_TRACE_PART = TraceDataPart('waltTraceEvents')

ALL_TRACE_PARTS = {ANDROID_PROCESS_DATA_PART,
                   ATRACE_PART,
                   ATRACE_PROCESS_DUMP_PART,
                   CHROME_TRACE_PART,
                   CPU_TRACE_DATA,
                   TELEMETRY_PART}

ALL_TRACE_PARTS_RAW_NAMES = set(k.raw_field_name for k in ALL_TRACE_PARTS)

def _HasTraceFor(part, raw):
  assert isinstance(part, TraceDataPart)
  if part.raw_field_name not in raw:
    return False
  return len(raw[part.raw_field_name]) > 0


def _GetFilePathForTrace(trace, dir_path):
  """ Return path to a file that contains |trace|.

  Note: if |trace| is an instance of TraceFileHandle, this reuses the trace path
  that the trace file handle holds. Otherwise, it creates a new trace file
  in |dir_path| directory.
  """
  if isinstance(trace, TraceFileHandle):
    return trace.file_path
  with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False) as fp:
    if isinstance(trace, StringTypes):
      fp.write(trace)
    elif isinstance(trace, dict) or isinstance(trace, list):
      json.dump(trace, fp)
    else:
      raise TypeError('Trace is of unknown type.')
    return fp.name


class _TraceData(object):
  """Provides read access to traces collected from multiple tracing agents.

  Instances are created by calling the AsData() method on a TraceDataWriter.

  Note: this API allows direct access to trace data in memory and, thus,
  may require a lot of memory if the traces to process are very large.
  This has lead to OOM errors in Telemetry in the past (e.g. crbug/672097).

  TODO(crbug/928278): This object is provided only to support legacy TBMv1
  metric computation, and should be removed when no such clients remain. New
  clients should instead call SerializeAsHtml() on the TraceDataWriter and
  pass the serialized output to an external trace processing script.
  """
  def __init__(self, raw_data):
    self._raw_data = raw_data

  @property
  def active_parts(self):
    return {p for p in ALL_TRACE_PARTS if p.raw_field_name in self._raw_data}

  def HasTracesFor(self, part):
    assert isinstance(part, TraceDataPart)
    traces = self._raw_data.get(part.raw_field_name)
    return traces is not None and len(traces) > 0

  def GetTracesFor(self, part):
    """Return the list of traces for |part| in string or dictionary forms."""
    if not self.HasTracesFor(part):
      return []
    traces_list = self._raw_data[part.raw_field_name]
    # Since this API return the traces in memory form, and since the memory
    # bottleneck of Telemetry is for keeping trace in memory, there is no uses
    # in keeping the on-disk form of tracing beyond this point. Hence we convert
    # all traces for part of form TraceFileHandle to the JSON form.
    for i, data in enumerate(traces_list):
      if isinstance(data, TraceFileHandle):
        traces_list[i] = data.AsTraceData()
    return traces_list

  def GetTraceFor(self, part):
    traces = self.GetTracesFor(part)
    assert len(traces) == 1
    return traces[0]

  def CleanUpAllTraces(self):
    """Remove all the traces that this has handles to.

    TODO(crbug/928278): Move this method to TraceDataWriter.

    Those include traces stored in memory & on disk. After invoking this,
    one can no longer uses this object for reading the trace data.
    """
    for traces_list in self._raw_data.values():
      for trace in traces_list:
        if isinstance(trace, TraceFileHandle):
          trace.Clean()
    self._raw_data = {}

  def Serialize(self, file_path, trace_title=''):
    """Serializes the trace result to |file_path|.

    TODO(crbug/928278): Move this method to TraceDataWriter.
    """
    if not self._raw_data:
      logging.warning('No traces to convert to html.')
      return
    temp_dir = tempfile.mkdtemp()
    trace_files = []
    try:
      trace_size_data = {}
      for part, traces_list in self._raw_data.items():
        for trace in traces_list:
          path = _GetFilePathForTrace(trace, temp_dir)
          trace_size_data.setdefault(part, 0)
          trace_size_data[part] += os.path.getsize(path)
          trace_files.append(path)
      logging.info('Trace sizes in bytes: %s', trace_size_data)

      start_time = time.time()
      cmd = (
          ['python', _TRACE2HTML_PATH] + trace_files +
          ['--output', file_path] + ['--title', trace_title])
      subprocess.check_output(cmd)

      elapsed_time = time.time() - start_time
      logging.info('trace2html finished in %.02f seconds.', elapsed_time)
    finally:
      shutil.rmtree(temp_dir)


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
  def __init__(self, compressed):
    self._backing_file = None
    self._file_path = None
    self._trace_data = None
    self._compressed = compressed

  def Open(self):
    assert not self._backing_file and not self._file_path
    self._backing_file = tempfile.NamedTemporaryFile(delete=False, mode='ab')

  def AppendTraceData(self, partial_trace_data, b64=False):
    assert isinstance(partial_trace_data, StringTypes)
    self._backing_file.write(
        base64.b64decode(partial_trace_data) if b64 else partial_trace_data)

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

  def AsTraceData(self):
    """Get the object form of trace data that this handle manages.

    *Warning: this can have large memory footprint if the trace data is big.

    Since this requires the in-memory form of the trace, it is no longer useful
    to still keep the backing file underneath, invoking this will also discard
    the file to avoid the risk of leaking the backing trace file.
    """
    if self._trace_data:
      return self._trace_data
    assert self._file_path
    opn = gzip.open if self._compressed else open
    with opn(self._file_path, 'rb') as f:
      self._trace_data = json.load(f)
    self.Clean()
    return self._trace_data

  def Clean(self):
    """Remove the backing file used for storing trace on disk.

    This should be called when and only when you no longer need to use
    TraceFileHandle.
    """
    assert self._file_path
    os.remove(self._file_path)
    self._file_path = None


class TraceDataBuilder(object):
  """TraceDataBuilder helps build up a trace from multiple trace agents.

  TODO(crbug/928278): This class is meant to become the "write only" part
  of data collection. Clients should be able to collect and serialized merged
  trace data using this object, without having to call AsData() which provides
  the "trace reading" service for legacy clients.
  """
  def __init__(self):
    self._raw_data = {}

  def AsData(self):
    """Allow in-memory access to read the collected trace data.

    TODO(crbug/928278): This method is only provided to support legacy TBMv1
    metric computation, and should be removed when no such clients remain.
    """
    if self._raw_data is None:
      raise Exception('Can only AsData once')
    data = _TraceData(self._raw_data)
    self._raw_data = None
    return data

  def AddTraceFor(self, part, trace):
    assert isinstance(part, TraceDataPart), part
    if part == CHROME_TRACE_PART:
      assert (isinstance(trace, dict) or
              isinstance(trace, list) or
              isinstance(trace, TraceFileHandle))
    else:
      assert (isinstance(trace, StringTypes) or
              isinstance(trace, dict) or
              isinstance(trace, list))

    if self._raw_data is None:
      raise Exception('Already called AsData() on this builder.')

    self._raw_data.setdefault(part.raw_field_name, [])
    self._raw_data[part.raw_field_name].append(trace)


def CreateTraceDataFromRawData(raw_data):
  """Convenient method for creating a _TraceData object from |raw_data|.

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
  if isinstance(raw_data, StringTypes):
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
