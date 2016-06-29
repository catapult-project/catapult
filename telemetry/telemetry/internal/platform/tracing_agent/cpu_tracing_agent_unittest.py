# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import sys
import time
import unittest

from telemetry import decorators
from telemetry.internal.platform.tracing_agent import cpu_tracing_agent
from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform import linux_platform_backend
from telemetry.internal.platform import mac_platform_backend
from telemetry.internal.platform import win_platform_backend
from telemetry.timeline import trace_data
from telemetry.timeline import tracing_config

SNAPSHOT_KEYS = {'mac': ['pid', 'command', 'pCpu', 'pMem'],
                'linux': ['pid', 'command', 'pCpu', 'pMem'],
                'win': ['pid', 'command', 'pCpu']}
TRACE_EVENT_KEYS = ['name', 'tid', 'pid', 'ph', 'args', 'local', 'id', 'ts']


class FakeAndroidPlatformBackend(object):
  def __init__(self):
    self.device = 'fake_device'

  def GetOSName(self):
    return 'android'


# TODO(ziqi): enable tests on win (https://github.com/catapult-project/catapult/issues/2439)
class CpuTracingAgentTest(unittest.TestCase):

  def setUp(self):
    self._config = tracing_config.TracingConfig()
    self._config.enable_cpu_trace = True
    if sys.platform.startswith('win'):
      self._desktop_backend = win_platform_backend.WinPlatformBackend()
    elif sys.platform.startswith('darwin'):
      self._desktop_backend = mac_platform_backend.MacPlatformBackend()
    else:
      self._desktop_backend = linux_platform_backend.LinuxPlatformBackend()
    self._agent = cpu_tracing_agent.CpuTracingAgent(self._desktop_backend)

  @decorators.Enabled('linux', 'mac')
  def testInit(self):
    self.assertTrue(isinstance(self._agent,
                               tracing_agent.TracingAgent))
    self.assertFalse(self._agent._snapshots)
    self.assertFalse(self._agent._snapshot_ongoing)

  @decorators.Enabled('linux', 'mac')
  def testIsSupported(self):
    self.assertTrue(cpu_tracing_agent.CpuTracingAgent.IsSupported(
      self._desktop_backend))
    self.assertFalse(cpu_tracing_agent.CpuTracingAgent.IsSupported(
      FakeAndroidPlatformBackend()))

  @decorators.Enabled('linux', 'mac')
  def testStartAgentTracing(self):
    self.assertFalse(self._agent._snapshot_ongoing)
    self.assertFalse(self._agent._snapshots)
    self.assertTrue(self._agent.StartAgentTracing(self._config, 0))
    self.assertTrue(self._agent._snapshot_ongoing)
    time.sleep(2)
    self.assertTrue(self._agent._snapshots)

  @decorators.Enabled('linux', 'mac')
  def testStartAgentTracingNotEnabled(self):
    self._config.enable_cpu_trace = False
    self.assertFalse(self._agent._snapshot_ongoing)
    self.assertFalse(self._agent.StartAgentTracing(self._config, 0))
    self.assertFalse(self._agent._snapshot_ongoing)
    self.assertFalse(self._agent._snapshots)
    time.sleep(2)
    self.assertFalse(self._agent._snapshots)

  @decorators.Enabled('linux', 'mac')
  def testStopAgentTracingBeforeStart(self):
    self.assertRaises(AssertionError, self._agent.StopAgentTracing)

  @decorators.Enabled('linux', 'mac')
  def testStopAgentTracing(self):
    self._agent.StartAgentTracing(self._config, 0)
    self._agent.StopAgentTracing()
    self.assertFalse(self._agent._snapshot_ongoing)

  @decorators.Enabled('linux', 'mac')
  def testCollectAgentTraceDataBeforeStart(self):
    self.assertRaises(AssertionError, self._agent.CollectAgentTraceData,
                      trace_data.TraceDataBuilder())

  @decorators.Enabled('linux', 'mac')
  def testCollectAgentTraceData(self):
    builder = trace_data.TraceDataBuilder()
    self._agent.StartAgentTracing(self._config, 0)
    self._agent.CollectAgentTraceData(builder)
    self.assertFalse(self._agent._snapshot_ongoing)
    builder = builder.AsData()
    self.assertTrue(builder.HasTraceFor(trace_data.CPU_TRACE_DATA))

  @decorators.Enabled('linux', 'mac')
  def testCollectAgentTraceDataFormat(self):
    builder = trace_data.TraceDataBuilder()
    self._agent.StartAgentTracing(self._config, 0)
    time.sleep(2)
    self._agent.CollectAgentTraceData(builder)
    builder = builder.AsData()
    data = json.loads(builder.GetTraceFor(trace_data.CPU_TRACE_DATA))
    self.assertTrue(data)
    self.assertEquals(set(data[0].keys()), set(TRACE_EVENT_KEYS))
    self.assertEquals(set(data[0]['args'].keys()), set(['processes']))
    self.assertTrue(data[0]['args']['processes'])
    self.assertEquals(set(data[0]['args']['processes'][0].keys()),
                      set(SNAPSHOT_KEYS[self._desktop_backend.GetOSName()]))
