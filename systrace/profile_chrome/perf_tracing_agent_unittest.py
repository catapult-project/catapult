# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from profile_chrome import agents_unittest
from profile_chrome import perf_tracing_agent
from profile_chrome import ui


class PerfProfilerAgentTest(agents_unittest.BaseAgentTest):
  def testGetCategories(self):
    if not perf_tracing_agent.PerfProfilerAgent.IsSupported():
      return
    categories = \
        perf_tracing_agent.PerfProfilerAgent.GetCategories(self.device)
    assert 'cycles' in ' '.join(categories)

  def testTracing(self):
    if not perf_tracing_agent.PerfProfilerAgent.IsSupported():
      return
    ui.EnableTestMode()
    categories = ['cycles']
    agent = perf_tracing_agent.PerfProfilerAgent(self.device,
                                                 categories)

    try:
      agent.StartAgentTracing(None, None)
    finally:
      agent.StopAgentTracing()

    result = agent.GetResults()
    json.loads(result.raw_data)
