#!/usr/bin/env python

# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Implementation of tracing controller for systrace. This class creates the
necessary tracing agents for systrace, runs them, and outputs the results
as an HTML or JSON file.'''

import json
import os

from systrace import tracing_controller
from systrace.tracing_agents import atrace_agent
from systrace.tracing_agents import atrace_from_file_agent
from systrace.tracing_agents import battor_trace_agent
from systrace.tracing_agents import ftrace_agent

AGENT_MODULES_ = [atrace_agent, atrace_from_file_agent,
                 battor_trace_agent, ftrace_agent]


# TODO(alexandermont): Current version of trace viewer does not support
# the controller tracing agent output. Thus we use this variable to
# suppress this tracing agent's output. This should be removed once
# trace viewer is working again.
OUTPUT_CONTROLLER_TRACE_ = False


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

    # Update trace viewer if necessary.
    try:
      from systrace import update_systrace_trace_viewer
    except ImportError:
      pass
    else:
      update_systrace_trace_viewer.update(self._script_dir)

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
      self._WriteTraceJSON(self._tracing_controller.all_results)
    else:
      self._WriteTraceHTML(self._tracing_controller.all_results)

  def _WriteTraceJSON(self, results):
    """Write the results of systrace as a JSON file.

    Args:
        results: Results to write.
    """
    print 'Writing trace JSON'
    results['controllerTraceDataKey'] = 'traceEvents'
    if not OUTPUT_CONTROLLER_TRACE_:
      results['traceEvents'] = []
    with open(self._out_filename, 'w') as json_file:
      json.dump(results, json_file)
    print '\n    Wrote file://%s\n' % os.path.abspath(self._out_filename)

  def _WriteTraceHTML(self, results):
    """Write the results of systrace to an HTML file.
    """
    def _read_asset(src_dir, filename):
      return open(os.path.join(src_dir, filename)).read()

    # Get the trace viewer code and the prefix and suffix for the HTML.
    print 'Writing trace HTML'
    systrace_dir = os.path.abspath(os.path.dirname(__file__))
    html_prefix = _read_asset(systrace_dir, 'prefix.html')
    html_suffix = _read_asset(systrace_dir, 'suffix.html')
    trace_viewer_html = _read_asset(self._script_dir,
                                    'systrace_trace_viewer.html')

    # Open the file in binary mode to prevent python from changing the
    # line endings, then write the prefix.
    html_file = open(self._out_filename, 'wb')
    html_file.write(html_prefix.replace('{{SYSTRACE_TRACE_VIEWER_HTML}}',
                                        trace_viewer_html))

    # Write the trace data itself. There is a separate section of the form
    # <script class="trace-data" type="application/text"> ... </script>
    # for each tracing agent (including the controller tracing agent).
    html_file.write('<!-- BEGIN TRACE -->\n')
    for (name, data) in results.iteritems():
      if name == 'traceEvents' and not OUTPUT_CONTROLLER_TRACE_:
        continue
      html_file.write('  <script class="')
      html_file.write('trace-data')
      html_file.write('" type="application/text">\n')
      html_file.write(ConvertToHtmlString(data))
      html_file.write('  </script>\n')
    html_file.write('<!-- END TRACE -->\n')

    # Write the suffix and finish.
    html_file.write(html_suffix)
    html_file.close()
    print '\n    Wrote file://%s\n' % os.path.abspath(self._out_filename)

def ConvertToHtmlString(trace_result):
  """Convert a trace result to the format to be output into HTML.

  If the trace result is a dictionary or list, JSON-encode it.
  If the trace result is a string, leave it unchanged.
  """
  if isinstance(trace_result, dict) or isinstance(trace_result, list):
    return json.dumps(trace_result)
  elif isinstance(trace_result, str):
    return trace_result
  else:
    raise ValueError('Invalid trace result format for HTML output')

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
