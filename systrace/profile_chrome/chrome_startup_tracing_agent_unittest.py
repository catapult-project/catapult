# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from profile_chrome import chrome_startup_tracing_agent
from profile_chrome import agents_unittest


class ChromeAgentTest(agents_unittest.BaseAgentTest):
  def testTracing(self):
    agent = chrome_startup_tracing_agent.ChromeStartupTracingAgent(
        self.device, self.package_info, False, 'https://www.google.com')

    try:
      agent.StartAgentTracing(None, None)
    finally:
      agent.StopAgentTracing()

    result = agent.GetResults()
    json.loads(result.raw_data)
