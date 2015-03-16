# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.platform.tracing_agent import chrome_tracing_agent


class FakePlatformBackend(object):
  pass


class FakeDevtoolsClient(object):
  def __init__(self, remote_port):
    self.is_alive = True
    self.tracing_started = False
    self.remote_port = remote_port
    self.will_raise_exception_in_stop_tracing = False

  def IsAlive(self):
    return self.is_alive

  def StartChromeTracing(self, _trace_options, _filter_string, _timeout=10):
    self.tracing_started = True

  def StopChromeTracing(self, _trace_data_builder):
    self.tracing_started = False
    if self.will_raise_exception_in_stop_tracing:
      raise Exception

  def IsChromeTracingSupported(self):
    return True


class FakeTraceOptions(object):
  def __init__(self):
    self.enable_chrome_trace = True


class FakeCategoryFilter(object):
  def __init__(self):
    self.filter_string = 'foo'


class ChromeTracingAgentUnittest(unittest.TestCase):
  def setUp(self):
    self.platform1 = FakePlatformBackend()
    self.platform2 = FakePlatformBackend()
    self.platform3 = FakePlatformBackend()

  def StartTracing(self, platform_backend, enable_chrome_trace=True):
    assert chrome_tracing_agent.ChromeTracingAgent.IsSupported(platform_backend)
    agent = chrome_tracing_agent.ChromeTracingAgent(platform_backend)
    trace_options = FakeTraceOptions()
    trace_options.enable_chrome_trace = enable_chrome_trace
    agent.Start(trace_options, FakeCategoryFilter(), 10)
    return agent

  def StopTracing(self, tracing_agent):
    tracing_agent.Stop(None)

  def testRegisterDevtoolsClient(self):
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        FakeDevtoolsClient(1), self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        FakeDevtoolsClient(2), self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        FakeDevtoolsClient(3), self.platform1)

    tracing_agent_of_platform1 = self.StartTracing(self.platform1)

    with self.assertRaises(chrome_tracing_agent.ChromeTracingStartedError):
      chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
          FakeDevtoolsClient(4), self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        FakeDevtoolsClient(5), self.platform2)

    self.StopTracing(tracing_agent_of_platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        FakeDevtoolsClient(6), self.platform1)

  def testIsSupport(self):
    self.assertFalse(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform1))
    self.assertFalse(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform2))
    self.assertFalse(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform3))

    devtool1 = FakeDevtoolsClient(1)
    devtool2 = FakeDevtoolsClient(2)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool1, self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool2, self.platform2)
    devtool2.is_alive = False

    # Chrome tracing is only supported on platform 1 since only platform 1 has
    # an alive devtool.
    self.assertTrue(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform1))
    self.assertFalse(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform2))
    self.assertFalse(
        chrome_tracing_agent.ChromeTracingAgent.IsSupported(self.platform3))

  def testStartAndStopTracing(self):
    devtool1 = FakeDevtoolsClient(1)
    devtool2 = FakeDevtoolsClient(2)
    devtool3 = FakeDevtoolsClient(3)
    devtool4 = FakeDevtoolsClient(2)
    # Register devtools 1, 2, 3 on platform1 and devtool 4 on platform 2
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool1, self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool2, self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool3, self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool4, self.platform2)
    devtool2.is_alive = False

    tracing_agent1 = self.StartTracing(self.platform1)
    with self.assertRaises(chrome_tracing_agent.ChromeTracingStartedError):
      self.StartTracing(self.platform1)

    self.assertTrue(devtool1.tracing_started)
    self.assertFalse(devtool2.tracing_started)
    self.assertTrue(devtool3.tracing_started)
    # Devtool 4 shouldn't have tracing started although it has the same remote
    # port as devtool 2
    self.assertFalse(devtool4.tracing_started)

    self.StopTracing(tracing_agent1)
    self.assertFalse(devtool1.tracing_started)
    self.assertFalse(devtool2.tracing_started)
    self.assertFalse(devtool3.tracing_started)
    self.assertFalse(devtool4.tracing_started)
    # Test that it should be ok to start & stop tracing on platform1 again.
    tracing_agent1 = self.StartTracing(self.platform1)
    self.StopTracing(tracing_agent1)

    tracing_agent2 = self.StartTracing(self.platform2)
    self.assertTrue(devtool4.tracing_started)
    self.StopTracing(tracing_agent2)
    self.assertFalse(devtool4.tracing_started)

  def testExceptionRaisedInStopTracing(self):
    devtool1 = FakeDevtoolsClient(1)
    devtool2 = FakeDevtoolsClient(2)
    # Register devtools 1, 2 on platform 1
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool1, self.platform1)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool2, self.platform1)
    tracing_agent1 = self.StartTracing(self.platform1)

    self.assertTrue(devtool1.tracing_started)
    self.assertTrue(devtool2.tracing_started)

    devtool2.will_raise_exception_in_stop_tracing = True
    with self.assertRaises(chrome_tracing_agent.ChromeTracingStoppedError):
      self.StopTracing(tracing_agent1)

    devtool1.is_alive = False
    devtool2.is_alive = False
    # Register devtools 3 on platform 1 should not raise any exception.
    devtool3 = FakeDevtoolsClient(3)
    chrome_tracing_agent.ChromeTracingAgent.RegisterDevToolsClient(
        devtool3, self.platform1)

    # Start & Stop tracing on platform 1 should work just fine.
    tracing_agent2 = self.StartTracing(self.platform1)
    self.StopTracing(tracing_agent2)
