
# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import py_utils
import re

from devil.utils import cmd_helper

from systrace import tracing_agents
from systrace.tracing_agents import atrace_agent

# ADB sends this text to indicate the beginning of the trace data.
TRACE_START_REGEXP = r'TRACE\:'
# Text that ADB sends, but does not need to be displayed to the user.
ADB_IGNORE_REGEXP = r'^capturing trace\.\.\. done|^capturing trace\.\.\.'

def try_create_agent(options):
  if options.from_file is not None:
    return AtraceFromFileAgent(options)
  else:
    return False

class AtraceFromFileAgent(tracing_agents.TracingAgent):
  def __init__(self, options):
    super(AtraceFromFileAgent, self).__init__()
    self._filename = options.from_file
    self._trace_data = False
    self._fix_circular_traces = options.fix_circular

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StartAgentTracing(self, options, categories, timeout=None):
    pass

  @py_utils.Timeout(tracing_agents.START_STOP_TIMEOUT)
  def StopAgentTracing(self, timeout=None):
    self._trace_data = self._read_trace_data()

  def SupportsExplicitClockSync(self):
    return False

  def RecordClockSyncMarker(self, sync_id, did_record_clock_sync_callback):
    raise NotImplementedError

  @py_utils.Timeout(tracing_agents.GET_RESULTS_TIMEOUT)
  def GetResults(self, timeout=None):
    return tracing_agents.TraceResult('trace-data', self._trace_data)

  def _read_trace_data(self):
    result = cmd_helper.GetCmdOutput(['cat', self._filename])
    data_start = re.search(TRACE_START_REGEXP, result).end(0)
    data = re.sub(ADB_IGNORE_REGEXP, '', result[data_start:])
    return self._preprocess_data(data)

  def _preprocess_data(self, data):
    # TODO: add fix_threads and fix_tgids options back in here
    # once we embed the dump data in the file (b/27504068)
    data = atrace_agent.strip_and_decompress_trace(data)
    if self._fix_circular_traces:
      data = atrace_agent.fix_circular_traces(data)
    return data
