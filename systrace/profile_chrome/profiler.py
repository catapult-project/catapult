# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil

from devil.android.constants import chrome
from profile_chrome import ui
from profile_chrome import util
from systrace import output_generator
from systrace import trace_result


def _StartTracing(controllers, interval):
  for controller in controllers:
    controller.StartTracing(interval)


def _StopTracing(controllers):
  for controller in controllers:
    controller.StopTracing()


def _PullTraces(controllers, output, compress, write_json):
  ui.PrintMessage('Downloading...', eol='')
  trace_files = [controller.PullTrace() for controller in controllers]
  trace_files = [trace for trace in trace_files if trace]
  if not trace_files:
    ui.PrintMessage('No results')
    return ''

  trace_files = output_generator.MergeTraceFilesIfNeeded(trace_files)
  if not write_json:
    print 'Writing trace HTML'
    html_file = os.path.splitext(trace_files[0])[0] + '.html'
    trace_results = _PrepareTracesForOutput(trace_files)
    result = output_generator.GenerateHTMLOutput(trace_results, html_file)
    print '\nWrote file://%s\n' % result
    trace_files = [html_file]
  if compress and len(trace_files) == 1:
    result = output or trace_files[0] + '.gz'
    util.CompressFile(trace_files[0], result)
  elif len(trace_files) > 1:
    result = (output or 'chrome-combined-trace-%s.zip' %
              util.GetTraceTimestamp())
    util.ArchiveFiles(trace_files, result)
  elif output:
    result = output
    shutil.move(trace_files[0], result)
  else:
    result = trace_files[0]

  return result


def _PrepareTracesForOutput(trace_files):
  trace_results = []
  for trace_file in trace_files:
    trace_name = trace_file.split('-')[0]
    with open(trace_file, 'r') as f:
      trace_data = f.read()
      trace_results.append(trace_result.TraceResult(trace_name, trace_data))
  return trace_results


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


def CaptureProfile(controllers, interval, output=None, compress=False,
                   write_json=False):
  """Records a profiling trace saves the result to a file.

  Args:
    controllers: List of tracing controllers.
    interval: Time interval to capture in seconds. An interval of None (or 0)
        continues tracing until stopped by the user.
    output: Output file name or None to use an automatically generated name.
    compress: If True, the result will be compressed either with gzip or zip
        depending on the number of captured subtraces.
    write_json: If True, prefer JSON output over HTML.

  Returns:
    Path to saved profile.
  """
  trace_type = ' + '.join(map(str, controllers))
  try:
    _StartTracing(controllers, interval)
    if interval:
      ui.PrintMessage(('Capturing %d-second %s. Press Enter to stop early...' %
                      (interval, trace_type)), eol='')
      ui.WaitForEnter(interval)
    else:
      ui.PrintMessage('Capturing %s. Press Enter to stop...' % trace_type,
                      eol='')
      raw_input()
  finally:
    _StopTracing(controllers)
  if interval:
    ui.PrintMessage('done')

  return _PullTraces(controllers, output, compress, write_json)
