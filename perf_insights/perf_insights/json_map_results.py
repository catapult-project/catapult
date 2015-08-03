# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from perf_insights import map_results
import json

class JSONMapResults(map_results.MapResults):
  def __init__(self, output_file):
    self.output_file = output_file
    self.run_infos = set()
    self.num_mapped_traces = 0
    self.num_failures = 0

  @property
  def had_failures(self):
    return self.num_failures > 0

  def WillMapTraces(self):
    self.output_file.write("""{
  "results" : [
""")
    self.output_file.flush()

  def WillMapSingleTrace(self, trace_handle):
    pass

  def DidMapSingleTrace(self, trace_handle, result_value):
    self.run_infos.add(trace_handle.run_info)

    if result_value['type'] == 'failure':
      self.num_failures += 1

    if self.num_mapped_traces > 0:
      self.output_file.write(',\n')
    self.num_mapped_traces += 1
    full_result = {
      'run': trace_handle.run_info.AsDict(),
      'metadata': trace_handle.metadata,
      'value': result_value
    }
    json.dump(full_result, self.output_file, indent=2)
    self.output_file.flush()

  def DidMapTraces(self):
    runs_table = dict([(run_info.run_id, run_info.AsDict())
                      for run_info in self.run_infos])

    self.output_file.write("""
  ]
}
""")
