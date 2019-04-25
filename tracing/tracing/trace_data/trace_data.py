# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
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


def _GetFilePathForTrace(trace, dir_path):
  """ Return path to a file that contains |trace|.

  Note: if |trace| is an instance of _TraceItem, this reuses the trace path
  that the trace file handle holds. Otherwise, it creates a new trace file
  in |dir_path| directory.
  """
  if isinstance(trace, _TraceItem):
    return trace.handle.name
  with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False) as fp:
    if isinstance(trace, StringTypes):
      fp.write(trace)
    elif isinstance(trace, dict) or isinstance(trace, list):
      json.dump(trace, fp)
    else:
      raise TypeError('Trace is of unknown type.')
    return fp.name


_TraceItem = collections.namedtuple(
    '_TraceItem', ['part_name', 'handle', 'compressed'])


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
    # all traces for part of form _TraceItem to the JSON form.
    for i, trace in enumerate(traces_list):
      if isinstance(trace, _TraceItem):
        opener = gzip.open if trace.compressed else open
        with opener(trace.handle.name, 'rb') as f:
          traces_list[i] = json.load(f)
        os.remove(trace.handle.name)
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
        if isinstance(trace, _TraceItem):
          os.remove(trace.handle.name)
    self._raw_data = {}

  def Serialize(self, file_path, trace_title=None):
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

      cmd = ['python', _TRACE2HTML_PATH]
      cmd.extend(trace_files)
      cmd.extend(['--output', file_path])
      if trace_title is not None:
        cmd.extend(['--title', trace_title])

      start_time = time.time()
      subprocess.check_output(cmd)
      elapsed_time = time.time() - start_time
      logging.info('trace2html finished in %.02f seconds.', elapsed_time)
    finally:
      shutil.rmtree(temp_dir)


class TraceDataBuilder(object):
  """TraceDataBuilder helps build up a trace from multiple trace agents.

  TODO(crbug/928278): This class is meant to become the "write only" part
  of data collection. Clients should be able to collect and serialized merged
  trace data using this object, without having to call AsData() which provides
  the "trace reading" service for legacy clients.
  """
  def __init__(self):
    self._raw_data = {}

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.CleanUpTraceData()

  def AsData(self):
    """Allow in-memory access to read the collected trace data.

    TODO(crbug/928278): This method is only provided to support legacy TBMv1
    metric computation, and should be removed when no such clients remain.
    """
    if self._raw_data is None:
      raise RuntimeError('Can only AsData once')
    data = _TraceData(self._raw_data)
    self._raw_data = None
    return data

  def OpenTraceHandleFor(self, part, compressed=False):
    """Open a file handle for writing trace data into it.

    Args:
      part: A TraceDataPart instance.
      compressed: An optional Boolean, indicates whether the written data is
        gzipped. Note, this information is currently only used by the AsData()
        method in order to be able to open and read the written data.
    """
    if not isinstance(part, TraceDataPart):
      raise TypeError('part must be a TraceDataPart instance')
    trace = _TraceItem(
        part_name=part.raw_field_name,
        handle=tempfile.NamedTemporaryFile(delete=False),
        compressed=compressed)
    self.AddTraceFor(part, trace)
    return trace.handle

  def AddTraceFileFor(self, part, trace_file):
    """Move a file with trace data into this builder.

    This is useful for situations where a client might want to start collecting
    trace data into a file, even before the TraceDataBuilder itself is created.

    Args:
      part: A TraceDataPart instance.
      trace_file: A path to a file containing trace data. Note: for efficiency
        the file is moved rather than copied into the builder. Therefore the
        source file will no longer exist after calling this method; and the
        lifetime of the trace data will thereafter be managed by this builder.
    """
    with self.OpenTraceHandleFor(part) as handle:
      pass
    if os.name == 'nt':
      # On windows os.rename won't overwrite, so the destination path needs to
      # be removed first.
      os.remove(handle.name)
    os.rename(trace_file, handle.name)

  def AddTraceFor(self, part, data, allow_unstructured=False):
    """Record new trace data into this builder.

    Args:
      part: A TraceDataPart instance.
      data: The trace data to write: a json-serializable dict, or unstructured
        text data as a string.
      allow_unstructured: This must be set to True to allow passing
        unstructured text data as input. Note: the use of this flag is
        discouraged and only exists to support legacy clients; new tracing
        agents should all produce structured trace data (e.g. proto or json).
    """
    if self._raw_data is None:
      raise RuntimeError('trace builder is no longer open for writing')
    if not isinstance(part, TraceDataPart):
      raise TypeError('part must be a TraceDataPart instance')
    if isinstance(data, StringTypes):
      if not allow_unstructured:
        raise ValueError('must pass allow_unstructured=True for text data')
    elif not isinstance(data, (dict, _TraceItem)):
      raise TypeError('invalid trace data type')

    self._raw_data.setdefault(part.raw_field_name, [])
    self._raw_data[part.raw_field_name].append(data)

  def CleanUpTraceData(self):
    """Clean up resources used by the data builder.

    Clients are responsible for calling this method when they are done
    serializing or extracting the written trace data.

    For convenience, clients may also use the TraceDataBuilder in a with
    statement for automated cleaning up, e.g.

        with trace_data.TraceDataBuilder() as builder:
          builder.AddTraceFor(trace_part, data)
          builder.Serialize(output_file)
    """
    if self._raw_data is None:
      return  # Owner of the raw trace data is now responsible for clean up.
    self.AsData().CleanUpAllTraces()

  def Serialize(self, file_path, trace_title=None):
    """Serialize the trace data to a file.

    Note: Due to implementation limitations, this also implicitly cleans up
    the trace data. However, clients shouldn't rely on this behavior and make
    sure to clean up the TraceDataBuilder themselves too.
    """
    data = self.AsData()
    try:
      data.Serialize(file_path, trace_title)
    finally:
      data.CleanUpAllTraces()


def CreateTestTrace(number=1):
  """Convenient helper method to create trace data objects for testing.

  Objects are created via the usual trace data writing route, so clients are
  also responsible for cleaning up trace data themselves.

  Clients are meant to treat these test traces as opaque. No guarantees are
  made about their contents, which they shouldn't try to read.
  """
  builder = TraceDataBuilder()
  builder.AddTraceFor(CHROME_TRACE_PART, {'traceEvents': [{'test': number}]})
  return builder.AsData()


def CreateFromRawChromeEvents(events):
  """Convenient helper to create trace data objects from raw Chrome events.

  This bypasses trace data writing, going directly to the in-memory json trace
  representation, so there is no need for trace file cleanup.

  This is used only for testing legacy clients that still read trace data.
  """
  assert isinstance(events, list)
  return _TraceData({
      CHROME_TRACE_PART.raw_field_name: [{'traceEvents': events}]})
