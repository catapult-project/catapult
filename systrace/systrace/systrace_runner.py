#!/usr/bin/env python

# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Implementation of tracing controller for systrace. This class creates the
necessary tracing agents for systrace, runs them, and outputs the results
as an HTML or JSON file.'''

from systrace import output_generator
from systrace import tracing_controller
from systrace.tracing_agents import atrace_agent
from systrace.tracing_agents import atrace_from_file_agent
from systrace.tracing_agents import battor_trace_agent
from systrace.tracing_agents import ftrace_agent


AGENT_MODULES_ = [atrace_agent, atrace_from_file_agent,
                 battor_trace_agent, ftrace_agent]


class SystraceRunner(object):
  def __init__(self, script_dir, options, categories):
    """Constructor.

    Args:
        script_dir: Directory containing the trace viewer script
                    (systrace_trace_viewer.html)
        options: List of command line options.
        categories: List of trace categories to capture.
    """
    # Parse command line arguments and create agents.
    self._script_dir = script_dir
    self._out_filename = options.output_file
    agents = CreateAgents(options)

    # Set up tracing controller.
    self._tracing_controller = tracing_controller.TracingController(options,
                                                                    categories,
                                                                    agents)

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

def CreateAgents(options):
  """Create tracing agents.

  This function will determine which tracing agents are valid given the
  options and create those agents.
  Args:
    options: The command-line options.
  Returns:
    The list of systrace agents.
  """
  result = [module.try_create_agent(options) for module in AGENT_MODULES_]
  return [x for x in result if x]
