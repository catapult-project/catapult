# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from profile_chrome import agents_unittest
from profile_chrome import ddms_tracing_agent


class DdmsAgentTest(agents_unittest.BaseAgentTest):
  def testTracing(self):
    agent = ddms_tracing_agent.DdmsAgent(self.device, self.package_info)

    try:
      agent.StartAgentTracing(None, None)
    finally:
      agent.StopAgentTracing()

    result = agent.GetResults()
    self.assertTrue(result.raw_data.startswith('*version'))
