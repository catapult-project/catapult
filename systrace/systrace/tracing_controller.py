#!/usr/bin/env python

# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Tracing controller class. This class manages
multiple tracing agents and collects data from all of them. It also
manages the clock sync process.
'''

import ast
import sys
import tempfile
import uuid

from devil.utils import reraiser_thread
from devil.utils import timeout_retry
from systrace import tracing_agents
from py_trace_event import trace_event

def ControllerAgentClockSync(name, issue_ts):
  '''Record the clock sync marker for controller tracing agent.

  Unlike with the other tracing agents, the tracing controller should not
  call this directly. Rather, it is called via callback from the other
  tracing agents when they write a trace.
  '''
  trace_event.clock_sync(name, issue_ts=issue_ts)


class TracingControllerAgent(tracing_agents.TracingAgent):
  def __init__(self):
    super(TracingControllerAgent, self).__init__()
    self._log_path = None

  def _StartAgentTracingImpl(self):
    """Start tracing for the controller tracing agent.

    Start tracing for the controller tracing agent. Note that
    the tracing controller records the "controller side"
    of the clock sync records, and nothing else.
    """
    if not trace_event.trace_can_enable():
      raise RuntimeError, ('Cannot enable trace_event;'
                           ' ensure catapult_base is in PYTHONPATH')

    controller_log_file = tempfile.NamedTemporaryFile(delete=False)
    self._log_path = controller_log_file.name
    controller_log_file.close()
    trace_event.trace_enable(self._log_path)
    return True

  def StartAgentTracing(self, options, categories, timeout=10):
    # pylint: disable=unused-argument
    # don't need the options and categories arguments in this
    # case, but including them for consistency with the
    # function prototypes for other TracingAgents
    return timeout_retry.Run(self._StartAgentTracingImpl,
                             timeout, 1)

  def _StopAgentTracingImpl(self):
    """Stops tracing for the controller tracing agent.
    """
    # pylint: disable=no-self-use
    # This function doesn't use self, but making it a member function
    # for consistency with the other TracingAgents
    trace_event.trace_disable()
    return True

  def StopAgentTracing(self, timeout=10):
    return timeout_retry.Run(self._StopAgentTracingImpl,
                             timeout, 1)

  def _GetResultsImpl(self):
    """Gets the log output from the controller tracing agent.

    This output only contains the "controller side" of the clock sync records.
    """
    with open(self._log_path, 'r') as outfile:
      result = outfile.read() + ']'
    return tracing_agents.TraceResult('traceEvents', ast.literal_eval(result))

  def GetResults(self, timeout=30):
    return timeout_retry.Run(self._GetResultsImpl,
                             timeout, 1)

  def SupportsExplicitClockSync(self):
    '''Returns whether this supports explicit clock sync.
    Although the tracing controller conceptually supports explicit clock
    sync, it is not an agent controlled by other controllers so it does not
    define RecordClockSyncMarker (rather, the recording of the "controller
    side" of the clock sync marker is done in _IssueClockSyncMarker). Thus,
    SupportsExplicitClockSync must return false.
    '''
    return False

  def RecordClockSyncMarker(self, sync_id, callback):
    raise NotImplementedError


class TracingController(object):
  def __init__(self, options, categories, agents):
    """Create tracing controller.

    Create a tracing controller object. Note that the tracing
    controller is also a tracing agent.

    Args:
       options: Tracing options.
       categories: Categories of trace events to record.
       agents: List of tracing agents for this controller.
    """
    self._child_agents = agents
    self._controller_agent = TracingControllerAgent()
    self._options = options
    self._categories = categories
    self._trace_in_progress = False

  def StartTracing(self):
    """Start tracing for all tracing agents.

    This function starts tracing for both the controller tracing agent
    and the child tracing agents.

    Returns:
        Boolean indicating whether or not the start tracing succeeded.
        Start tracing is considered successful if at least the
        controller tracing agent was started.
    """
    assert not self._trace_in_progress, 'Trace already in progress.'
    self._trace_in_progress = True

    # Start the controller tracing agents. Controller tracing agent
    # must be started successfully to proceed.
    if not self._controller_agent.StartAgentTracing(
        self._options,
        self._categories,
        timeout=self._options.timeout):
      print 'Unable to start controller tracing agent.'
      return False

    # Start the child tracing agents.
    succ_agents = []
    for agent in self._child_agents:
      if agent.StartAgentTracing(self._options,
                                 self._categories,
                                 timeout=self._options.timeout):
        succ_agents.append(agent)
      else:
        print 'Agent %s not started.' % str(agent)

    # Print warning if all agents not started.
    na = len(self._child_agents)
    ns = len(succ_agents)
    if ns < na:
      print 'Warning: Only %d of %d tracing agents started.' % (ns, na)
      self._child_agents = succ_agents
    return True

  def StopTracing(self):
    """Issue clock sync marker and stop tracing for all tracing agents.

    This function stops both the controller tracing agent
    and the child tracing agents. It issues a clock sync marker prior
    to stopping tracing.

    Returns:
        Boolean indicating whether or not the stop tracing succeeded
        for all agents.
    """
    assert self._trace_in_progress, 'No trace in progress.'
    self._trace_in_progress = False

    # Issue the clock sync marker and stop the child tracing agents.
    self._IssueClockSyncMarker()
    succ_agents = []
    for agent in self._child_agents:
      if agent.StopAgentTracing(timeout=self._options.timeout):
        succ_agents.append(agent)
      else:
        print 'Agent %s not stopped.' % str(agent)

    # Stop the controller tracing agent. Controller tracing agent
    # must be stopped successfully to proceed.
    if not self._controller_agent.StopAgentTracing(
        timeout=self._options.timeout):
      print 'Unable to stop controller tracing agent.'
      return False

    # Print warning if all agents not stopped.
    na = len(self._child_agents)
    ns = len(succ_agents)
    if ns < na:
      print 'Warning: Only %d of %d tracing agents stopped.' % (ns, na)
      self._child_agents = succ_agents

    # Collect the results from all the stopped tracing agents.
    all_results = {}
    for agent in self._child_agents + [self._controller_agent]:
      try:
        trace_result = agent.GetResults(
            timeout=self._options.collection_timeout)
        if trace_result.source_name in all_results:
          print 'Warning: Duplicate tracing agents'
        all_results[trace_result.source_name] = trace_result.raw_data
      # Check for exceptions. On timeout, continue; on other exceptions,
      # reraise and abort. Note that reraiser_thread.TimeoutError
      # will only be raised on a timeout error if the tracing agent
      # uses timeout_retry for timeout handling. A tracing agent using
      # a different timeout mechanism may generate a different exception.
      # In this case this code will re-raise that exception rather than
      # continuing with the other tracing agents, since this code won't
      # be able to identify that exception as a timeout exception.
      except reraiser_thread.TimeoutError:
        print 'Warning: Timeout when getting results from %s.' % str(agent)
      except:
        print 'Warning: Exception getting results from %s:' % str(agent)
        print sys.exc_info()[0]
        raise
    return all_results


  def _IssueClockSyncMarker(self):
    """Issue clock sync markers to all the child tracing agents."""
    for agent in self._child_agents:
      if agent.SupportsExplicitClockSync():
        sync_id = GetUniqueSyncID()
        agent.RecordClockSyncMarker(sync_id, ControllerAgentClockSync)

def GetUniqueSyncID():
  """Get a unique sync ID.

  Gets a unique sync ID by generating a UUID and converting it to a string
  (since UUIDs are not JSON serializable)
  """
  return str(uuid.uuid4())
