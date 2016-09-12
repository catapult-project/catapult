# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from profile_chrome import agents_unittest
from profile_chrome import atrace_tracing_agent
from systrace import decorators


class AtraceAgentTest(agents_unittest.BaseAgentTest):
  @decorators.ClientOnlyTest
  def testGetCategories(self):
    categories = \
        atrace_tracing_agent.AtraceAgent.GetCategories(self.device)
    self.assertTrue(categories)
    assert 'gfx' in ' '.join(categories)

  # TODO(washingtonp): This test throws an error on the Trybot servers when
  # running profile_chrome's atrace agent. Once systrace uses profile_chrome's
  # agent instead, this test may not longer need to be disabled.
  @decorators.Disabled
  def testTracing(self):
    categories = 'gfx,input,view'
    ring_buffer = False
    agent = atrace_tracing_agent.AtraceAgent(self.device,
                                             ring_buffer)

    try:
      agent.StartAgentTracing(atrace_tracing_agent.AtraceConfig(categories,
          self.device, ring_buffer))
    finally:
      agent.StopAgentTracing()
    result = agent.GetResults()

    self.assertFalse(agent.IsTracingOn())
    self.assertTrue('CPU#' in result.raw_data)
