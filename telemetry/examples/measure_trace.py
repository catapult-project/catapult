#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
from telemetry.page import page as page_module
from telemetry.results import buildbot_output_formatter
from telemetry.results import page_test_results
from telemetry.timeline import model
from telemetry.timeline import tracing_timeline_data
from telemetry.web_perf.metrics import smoothness
from telemetry.web_perf import timeline_interaction_record as tir_module

sys.path.append(os.path.join(
  os.path.dirname(__file__), os.pardir, os.pardir, 'perf'))
# pylint: disable=F0401
from measurements import smooth_gesture_util
from measurements import smoothness_controller


def _ExtractInteractionsRecordFromThread(thread, timeline_model):
  run_smooth_actions_record = None
  records = []
  for event in thread.async_slices:
    if not tir_module.IsTimelineInteractionRecord(event.name):
      continue
    assert event.start_thread
    assert event.start_thread is event.end_thread
    r = smooth_gesture_util.GetAdjustedInteractionIfContainGesture(
            timeline_model,
            tir_module.TimelineInteractionRecord.FromAsyncEvent(event))
    if r.label == smoothness_controller.RUN_SMOOTH_ACTIONS:
      assert run_smooth_actions_record is None, (
          'There can\'t be more than 1 %s record' %
          smoothness_controller.RUN_SMOOTH_ACTIONS)
      run_smooth_actions_record = r
    else:
      records.append(r)
  if not records:
    # Only include run_smooth_actions_record (label =
    # smoothness_controller.RUN_SMOOTH_ACTIONS) if there is no other records
    records = [run_smooth_actions_record]
  return records


def Main(args):
  if len(args) is not 1:
    print 'Invalid arguments. Usage: measure_trace.py <trace file>'
    return 1
  with open(args[0]) as trace_file:
    trace_data = tracing_timeline_data.TracingTimelineData(
        json.load(trace_file))

  timeline_model = model.TimelineModel(trace_data)
  smoothness_metric = smoothness.SmoothnessMetric()
  formatters = [
      buildbot_output_formatter.BuildbotOutputFormatter(sys.stdout)
      ]
  results = page_test_results.PageTestResults(output_formatters=formatters)
  for thread in timeline_model.GetAllThreads():
    interaction_records = _ExtractInteractionsRecordFromThread(
        thread, timeline_model)
    if not any(interaction_records):
      continue
    records_label_to_records_map = collections.defaultdict(list)
    for r in interaction_records:
      records_label_to_records_map[r.label].append(r)
    for label, records in records_label_to_records_map.iteritems():
      if records[0].is_smooth:
        page = page_module.Page('interaction-record://%s' % label)
        results.WillRunPage(page)
        smoothness_metric.AddResults(
            timeline_model, thread, records, results)
        results.DidRunPage(page)
  results.PrintSummary()
  return 0


if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
