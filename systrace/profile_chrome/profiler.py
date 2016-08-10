# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from devil.android.constants import chrome
from profile_chrome import chrome_tracing_agent
from profile_chrome import ui
from profile_chrome import util
from systrace import output_generator


def _StartTracing(agents):
  for agent in agents:
    agent.StartAgentTracing(None, None)


def _StopTracing(agents):
  for agent in agents:
    agent.StopAgentTracing()


def _GetResults(agents, output, compress, write_json, interval):
  ui.PrintMessage('Downloading...', eol='')

  # Wait for the trace file to get written.
  time.sleep(1)

  trace_results = []
  for agent in agents:
    if isinstance(agent, chrome_tracing_agent.ChromeTracingAgent):
      time.sleep(interval / 4)
    trace_results.append(agent.GetResults())

  if not trace_results:
    ui.PrintMessage('No results')
    return ''

  result = None
  trace_results = output_generator.MergeTraceResultsIfNeeded(trace_results)
  if not write_json:
    print 'Writing trace HTML'
    html_file = trace_results[0].source_name + '.html'
    result = output_generator.GenerateHTMLOutput(trace_results, html_file)
    print '\nWrote file://%s\n' % result
  elif compress and len(trace_results) == 1:
    result = output or trace_results[0].source_name + '.gz'
    util.WriteDataToCompressedFile(trace_results[0].raw_data, result)
  elif len(trace_results) > 1:
    result = (output or 'chrome-combined-trace-%s.zip' %
              util.GetTraceTimestamp())
    util.ArchiveData(trace_results, result)
  elif output:
    result = output
    with open(result, 'wb') as f:
      f.write(trace_results[0].raw_data)
  else:
    result = trace_results[0].source_name
    with open(result, 'wb') as f:
      f.write(trace_results[0].raw_data)

  return result


def GetSupportedBrowsers():
  """Returns the package names of all supported browsers."""
  # Add aliases for backwards compatibility.
  supported_browsers = {
    'stable': chrome.PACKAGE_INFO['chrome_stable'],
    'beta': chrome.PACKAGE_INFO['chrome_beta'],
    'dev': chrome.PACKAGE_INFO['chrome_dev'],
    'build': chrome.PACKAGE_INFO['chrome'],
  }
  supported_browsers.update(chrome.PACKAGE_INFO)
  return supported_browsers


def CaptureProfile(agents, interval, output=None, compress=False,
                   write_json=False):
  """Records a profiling trace saves the result to a file.

  Args:
    agents: List of tracing agents.
    interval: Time interval to capture in seconds. An interval of None (or 0)
        continues tracing until stopped by the user.
    output: Output file name or None to use an automatically generated name.
    compress: If True, the result will be compressed either with gzip or zip
        depending on the number of captured subtraces.
    write_json: If True, prefer JSON output over HTML.

  Returns:
    Path to saved profile.
  """
  trace_type = ' + '.join(map(str, agents))
  try:
    _StartTracing(agents)
    if interval:
      ui.PrintMessage(('Capturing %d-second %s. Press Enter to stop early...' %
                      (interval, trace_type)), eol='')
      ui.WaitForEnter(interval)
    else:
      ui.PrintMessage('Capturing %s. Press Enter to stop...' % trace_type,
                      eol='')
      raw_input()
  finally:
    _StopTracing(agents)
  if interval:
    ui.PrintMessage('done')

  return _GetResults(agents, output, compress, write_json, interval)
