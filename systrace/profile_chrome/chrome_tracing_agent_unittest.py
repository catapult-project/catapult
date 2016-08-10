# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from profile_chrome import chrome_tracing_agent
from profile_chrome import agents_unittest


class ChromeAgentTest(agents_unittest.BaseAgentTest):
  def testGetCategories(self):
    categories = \
        chrome_tracing_agent.ChromeTracingAgent.GetCategories(
            self.device, self.package_info)

    self.assertEquals(len(categories), 2)
    self.assertTrue(categories[0])
    self.assertTrue(categories[1])

  def testTracing(self):
    categories = '*'
    ring_buffer = False
    agent = chrome_tracing_agent.ChromeTracingAgent(self.device,
                                                    self.package_info,
                                                    categories,
                                                    ring_buffer)

    agent.StartAgentTracing(None, None)
    agent.StopAgentTracing()
    result = agent.GetResults()
    json.loads(result.raw_data)
