# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import tempfile

from tracing.mre import map_single_trace


_GET_TIMELINE_MARKERS = """
function processTrace(results, model) {
    var markers = [];
    for (const thread of model.getAllThreads()) {
        for (const event of thread.asyncSliceGroup.slices) {
            if (event.category === 'blink.console') {
                markers.push(event.title);
            }
        }
    }
    results.addPair('markers', markers);
};
"""

_GET_MEMORY_DUMP_EVENT_IDS = """
function processTrace(results, model) {
    var event_ids = [];
    for (const thread of model.getAllThreads()) {
        for (const event of thread.asyncSliceGroup.slices) {
            if (event.title === 'GlobalMemoryDump') {
                  event_ids.push(event.id);
            }
        }
    }
    results.addPair('event_ids', event_ids);
};
"""


def _SerializeAndProcessTrace(trace_data, process_trace_func_code):
  temp_dir = tempfile.mkdtemp()
  try:
    trace_file_path = os.path.join(temp_dir, 'temp_trace')
    trace_data.Serialize(trace_file_path)
    return map_single_trace.ExecuteTraceMappingCode(
        trace_file_path, process_trace_func_code)
  finally:
    shutil.rmtree(temp_dir)


def ExtractTimelineMarkers(trace_data):
  """Get a list with the titles of 'blink.console' events found in a trace.

  This will include any events that were inserted using tab.AddTimelineMarker
  while a trace was being recorded.

  The current implementation works by loading the trace data into the TBMv2,
  i.e. JavaScript based, timeline model. But this is an implementation detail,
  clients remain agnostic about the model used for trace processing.
  """
  return _SerializeAndProcessTrace(trace_data, _GET_TIMELINE_MARKERS)['markers']


def ExtractMemoryDumpIds(trace_data):
  """Get a list with the ids of 'GlobalMemoryDump' events found in a trace.

  The current implementation works by loading the trace data into the TBMv2,
  i.e. JavaScript based, timeline model. But this is an implementation detail,
  clients remain agnostic about the model used for trace processing.
  """
  event_ids = _SerializeAndProcessTrace(
      trace_data, _GET_MEMORY_DUMP_EVENT_IDS)['event_ids']
  # Event ids look like this: 'disabled-by-default-memory-infra:87890:ptr:0x3'.
  # The part after the last ':' is the dump id.
  return [eid.rsplit(':')[-1] for eid in event_ids]

