# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from profile_chrome import agents_unittest
from profile_chrome import atrace_tracing_agent


class AtraceAgentTest(agents_unittest.BaseAgentTest):
  def testGetCategories(self):
    categories = \
        atrace_tracing_agent.AtraceAgent.GetCategories(self.device)
    self.assertTrue(categories)
    assert 'gfx' in ' '.join(categories)

  def testTracing(self):
    categories = ['gfx', 'input', 'view']
    ring_buffer = False
    agent = atrace_tracing_agent.AtraceAgent(self.device,
                                             categories,
                                             ring_buffer)

    try:
      agent.StartAgentTracing(None, None)
    finally:
      agent.StopAgentTracing()
    result = agent.GetResults()

    self.assertFalse(agent.IsTracingOn())
    self.assertTrue('CPU#' in result.raw_data)
