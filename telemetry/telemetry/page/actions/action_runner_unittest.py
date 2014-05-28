# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from telemetry.core.backends.chrome import tracing_backend
from telemetry.core.timeline import model
from telemetry.page.actions import action_runner as action_runner_module
# pylint: disable=W0401,W0614
from telemetry.page.actions.all_page_actions import *
from telemetry.unittest import tab_test_case
from telemetry.web_perf import timeline_interaction_record as tir_module


class ActionRunnerTest(tab_test_case.TabTestCase):
  def testIssuingInteractionRecord(self):
    action_runner = action_runner_module.ActionRunner(self._tab)
    self.Navigate('interaction_enabled_page.html')
    action_runner.RunAction(WaitAction({'seconds': 1}))
    self._browser.StartTracing(tracing_backend.DEFAULT_TRACE_CATEGORIES)
    action_runner.BeginInteraction('TestInteraction', [tir_module.IS_SMOOTH])
    action_runner.EndInteraction('TestInteraction', [tir_module.IS_SMOOTH])
    trace_data = self._browser.StopTracing()
    timeline_model = model.TimelineModel(trace_data)

    records = []
    renderer_thread = timeline_model.GetRendererThreadFromTab(self._tab)
    for event in renderer_thread.async_slices:
      if not tir_module.IsTimelineInteractionRecord(event.name):
        continue
      records.append(tir_module.TimelineInteractionRecord.FromAsyncEvent(event))
    self.assertEqual(1, len(records),
                     'Fail to issue the interaction record on tracing timeline.'
                     ' Trace data:\n%s' % repr(trace_data.EventData()))
    self.assertEqual('TestInteraction', records[0].logical_name)
    self.assertTrue(records[0].is_smooth)
