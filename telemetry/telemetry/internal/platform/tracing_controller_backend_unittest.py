# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the tracing_controller_backend.

These are written to test the public API of the TracingControllerBackend,
using a mock platform and mock tracing agents.

Integrations tests using a real running browser and tracing agents are included
among tests for the public facing telemetry.core.tracing_controller.
"""

import unittest

from telemetry import decorators
from telemetry.internal.platform import platform_backend
from telemetry.internal.platform import tracing_agent
from telemetry.internal.platform import tracing_controller_backend
from telemetry.timeline import tracing_config

import mock


def MockAgentClass(can_start=True, supports_clock_sync=True):
  """Factory to create mock tracing agent classes."""
  def record_clock_sync_marker(sync_id, callback):
    callback(sync_id, 1)

  agent = mock.Mock(spec=tracing_agent.TracingAgent)
  agent.StartAgentTracing.return_value = can_start
  agent.SupportsExplicitClockSync.return_value = supports_clock_sync
  agent.RecordClockSyncMarker.side_effect = record_clock_sync_marker
  AgentClass = mock.Mock(return_value=agent)
  AgentClass.IsSupported.return_value = True
  return AgentClass


class FakeTraceDataBuilder(object):
  """Discards trace data but used to keep track of clock syncs."""
  def __init__(self):
    self.clock_syncs = []

  def AddTraceFor(self, trace_part, value):
    del trace_part  # Unused.
    del value  # Unused.

  def AsData(self):
    return self


class TracingControllerBackendTest(unittest.TestCase):
  def setUp(self):
    # Create a real TracingControllerBackend with a mock platform backend.
    mock_platform = mock.Mock(spec=platform_backend.PlatformBackend)
    self.controller = (
        tracing_controller_backend.TracingControllerBackend(mock_platform))
    self.config = tracing_config.TracingConfig()

    # Replace the list of real tracing agent classes, with a single simple
    # mock agent class. Tests can also override this list.
    self._TRACING_AGENT_CLASSES = []
    mock.patch(
        'telemetry.internal.platform.tracing_controller_backend'
        '._TRACING_AGENT_CLASSES', new=self._TRACING_AGENT_CLASSES).start()
    self._SetTracingAgentClasses(MockAgentClass())

    # Replace the real TraceDataBuilder with our fake one, also wire it up
    # so we can keep track of trace_event.clock_sync calls.
    def clock_sync(sync_id, issue_ts):
      del issue_ts  # Unused.
      self.controller._current_state.builder.clock_syncs.append(sync_id)

    mock.patch('tracing.trace_data.trace_data.TraceDataBuilder',
               new=FakeTraceDataBuilder).start()
    mock.patch('py_trace_event.trace_event.clock_sync',
               side_effect=clock_sync).start()

  def tearDown(self):
    if self.controller.is_tracing_running:
      self.controller.StopTracing()
    mock.patch.stopall()

  def _SetTracingAgentClasses(self, *agent_classes):
    # Replace contents of the list with the agent classes given as args.
    self._TRACING_AGENT_CLASSES[:] = agent_classes

  @decorators.Isolated
  def testStartTracing(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)

  @decorators.Isolated
  def testDoubleStartTracing(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertFalse(self.controller.StartTracing(self.config, 30))

  @decorators.Isolated
  def testStopTracingNotStarted(self):
    with self.assertRaises(AssertionError):
      self.controller.StopTracing()

  @decorators.Isolated
  def testStopTracing(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    data = self.controller.StopTracing()
    self.assertEqual(len(data.clock_syncs), 1)
    self.assertFalse(self.controller.is_tracing_running)

  @decorators.Isolated
  def testDoubleStopTracing(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    data = self.controller.StopTracing()
    self.assertEqual(len(data.clock_syncs), 1)
    self.assertFalse(self.controller.is_tracing_running)
    with self.assertRaises(AssertionError):
      self.controller.StopTracing()

  @decorators.Isolated
  def testMultipleStartStop(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    data = self.controller.StopTracing()
    self.assertEqual(len(data.clock_syncs), 1)
    sync_event_one = data.clock_syncs[0]
    self.assertFalse(self.controller.is_tracing_running)
    # Run 2
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    data = self.controller.StopTracing()
    self.assertEqual(len(data.clock_syncs), 1)
    sync_event_two = data.clock_syncs[0]
    self.assertFalse(self.controller.is_tracing_running)
    # Test difference between events
    self.assertNotEqual(sync_event_one, sync_event_two)

  @decorators.Isolated
  def testCollectAgentDataBeforeStoppingTracing(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    with self.assertRaises(AssertionError):
      self.controller.CollectAgentTraceData(None)

  @decorators.Isolated
  def testFlush(self):
    self.assertFalse(self.controller.is_tracing_running)
    self.assertIsNone(self.controller._current_state)

    # Start tracing.
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertIs(self.controller._current_state.config, self.config)
    self.assertEqual(self.controller._current_state.timeout, 30)
    self.assertIsNotNone(self.controller._current_state.builder)

    # Flush tracing several times.
    for _ in xrange(5):
      self.controller.FlushTracing()
      self.assertTrue(self.controller.is_tracing_running)
      self.assertIs(self.controller._current_state.config, self.config)
      self.assertEqual(self.controller._current_state.timeout, 30)
      self.assertIsNotNone(self.controller._current_state.builder)

    # Stop tracing.
    data = self.controller.StopTracing()
    self.assertFalse(self.controller.is_tracing_running)
    self.assertIsNone(self.controller._current_state)

    self.assertEqual(len(data.clock_syncs), 6)

  @decorators.Isolated
  def testNonWorkingAgent(self):
    self._SetTracingAgentClasses(MockAgentClass(can_start=False))
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertEquals(self.controller._active_agents_instances, [])
    data = self.controller.StopTracing()
    self.assertEqual(len(data.clock_syncs), 0)
    self.assertFalse(self.controller.is_tracing_running)

  @decorators.Isolated
  def testNoClockSyncSupport(self):
    self._SetTracingAgentClasses(MockAgentClass(supports_clock_sync=False))
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertEquals(len(self.controller._active_agents_instances), 1)
    data = self.controller.StopTracing()
    self.assertFalse(self.controller.is_tracing_running)
    self.assertEqual(len(data.clock_syncs), 0)

  @decorators.Isolated
  def testMultipleAgents(self):
    # Only 4 agents can start and, from those, only 2 support clock sync.
    self._SetTracingAgentClasses(
        MockAgentClass(),
        MockAgentClass(),
        MockAgentClass(can_start=False),
        MockAgentClass(can_start=False),
        MockAgentClass(supports_clock_sync=False),
        MockAgentClass(supports_clock_sync=False)
    )
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertEquals(len(self.controller._active_agents_instances), 4)
    data = self.controller.StopTracing()
    self.assertFalse(self.controller.is_tracing_running)
    self.assertEqual(len(data.clock_syncs), 2)

  @decorators.Isolated
  @mock.patch('py_trace_event.trace_event.is_tracing_controllable')
  def testIssueClockSyncMarker_tracingNotControllable(self, is_controllable):
    is_controllable.return_value = False
    self._SetTracingAgentClasses(
        MockAgentClass(),
        MockAgentClass(),
        MockAgentClass(can_start=False),
        MockAgentClass(can_start=False),
        MockAgentClass(supports_clock_sync=False),
        MockAgentClass(supports_clock_sync=False)
    )
    self.assertFalse(self.controller.is_tracing_running)
    self.assertTrue(self.controller.StartTracing(self.config, 30))
    self.assertTrue(self.controller.is_tracing_running)
    self.assertEquals(len(self.controller._active_agents_instances), 4)
    data = self.controller.StopTracing()
    self.assertFalse(self.controller.is_tracing_running)
    self.assertEqual(len(data.clock_syncs), 0)  # No clock syncs found.
