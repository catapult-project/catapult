#!/usr/bin/env python

# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Implementation of tracing controller for systrace. This class creates the
necessary tracing agents for systrace, runs them, and outputs the results
as an HTML or JSON file.'''

from systrace import output_generator
from systrace import tracing_agents
from systrace import tracing_controller
from systrace.tracing_agents import atrace_agent
from systrace.tracing_agents import atrace_from_file_agent
from systrace.tracing_agents import battor_trace_agent
from systrace.tracing_agents import ftrace_agent


AGENT_MODULES_ = [atrace_agent, atrace_from_file_agent,
                 battor_trace_agent, ftrace_agent]


class SystraceRunner(object):
  def __init__(self, script_dir, options):
    """Constructor.

    Args:
        script_dir: Directory containing the trace viewer script
                    (systrace_trace_viewer.html)
        options: Object containing command line options.
    """
    # Parse command line arguments and create agents.
    self._script_dir = script_dir
    self._out_filename = options.output_file
    agents_with_config = _CreateAgentsWithConfig(options)
    controller_config = _GetControllerConfig(options)

    # Set up tracing controller.
    self._tracing_controller = tracing_controller.TracingController(
        agents_with_config, controller_config)

  def StartTracing(self):
    self._tracing_controller.StartTracing()

  def StopTracing(self):
    self._tracing_controller.StopTracing()

  def OutputSystraceResults(self, write_json=False):
    """Output the results of systrace to a file.

    If output is necessary, then write the results of systrace to either (a)
    a standalone HTML file, or (b) a json file which can be read by the
    trace viewer.

    Args:
       write_json: Whether to output to a json file (if false, use HTML file)
    """
    print 'Tracing complete, writing results'
    if write_json:
      result = output_generator.GenerateJSONOutput(
                  self._tracing_controller.all_results,
                  self._out_filename)
    else:
      result = output_generator.GenerateHTMLOutput(
                  self._tracing_controller.all_results,
                  self._out_filename)
    print '\nWrote trace %s file: file://%s\n' % (('JSON' if write_json
                                                   else 'HTML'), result)


class AgentWithConfig(object):
  def __init__(self, agent, config):
    self.agent = agent
    self.config = config


def _CreateAgentsWithConfig(options):
  """Create tracing agents.

  This function will determine which tracing agents are valid given the
  options and create those agents along with their corresponding configuration
  object.
  Args:
    options: The command-line options.
  Returns:
    A list of AgentWithConfig options containing agents and their corresponding
    configuration object.
  """
  result = []
  for module in AGENT_MODULES_:
    config = module.get_config(options)
    agent = module.try_create_agent(config)
    if agent and config:
      result.append(AgentWithConfig(agent, config))
  return [x for x in result if x and x.agent]


class TracingControllerConfig(tracing_agents.TracingConfig):
  def __init__(self, output_file, trace_time, list_categories, write_json,
               link_assets, asset_dir, timeout, collection_timeout,
               device_serial_number, target):
    tracing_agents.TracingConfig.__init__(self)
    self.output_file = output_file
    self.trace_time = trace_time
    self.list_categories = list_categories
    self.write_json = write_json
    self.link_assets = link_assets
    self.asset_dir = asset_dir
    self.timeout = timeout
    self.collection_timeout = collection_timeout
    self.device_serial_number = device_serial_number
    self.target = target


def _GetControllerConfig(options):
  return TracingControllerConfig(options.output_file, options.trace_time,
                                 options.list_categories, options.write_json,
                                 options.link_assets, options.asset_dir,
                                 options.timeout, options.collection_timeout,
                                 options.device_serial_number, options.target)
