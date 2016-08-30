#!/usr/bin/env python
#
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import optparse
import os
import sys
import webbrowser

from profile_chrome import chrome_tracing_agent
from profile_chrome import ddms_tracing_agent
from profile_chrome import flags
from profile_chrome import perf_tracing_agent
from profile_chrome import profiler
from profile_chrome import atrace_tracing_agent
from profile_chrome import ui

from devil.android import device_utils


PROFILE_CHROME_AGENT_MODULES = [chrome_tracing_agent, ddms_tracing_agent,
                                perf_tracing_agent, atrace_tracing_agent]


def _CreateOptionParser():
  parser = optparse.OptionParser(description='Record about://tracing profiles '
                                 'from Android browsers. See http://dev.'
                                 'chromium.org/developers/how-tos/trace-event-'
                                 'profiling-tool for detailed instructions for '
                                 'profiling.')

  timed_options = optparse.OptionGroup(parser, 'Timed tracing')
  timed_options.add_option('-t', '--time', help='Profile for N seconds and '
                          'download the resulting trace.', metavar='N',
                           type='float')
  parser.add_option_group(timed_options)

  cont_options = optparse.OptionGroup(parser, 'Continuous tracing')
  cont_options.add_option('--continuous', help='Profile continuously until '
                          'stopped.', action='store_true')
  cont_options.add_option('--ring-buffer', help='Use the trace buffer as a '
                          'ring buffer and save its contents when stopping '
                          'instead of appending events into one long trace.',
                          action='store_true')
  parser.add_option_group(cont_options)

  parser.add_option_group(flags.OutputOptions(parser))

  browsers = sorted(profiler.GetSupportedBrowsers().keys())
  parser.add_option('-b', '--browser', help='Select among installed browsers. '
                    'One of ' + ', '.join(browsers) + ', "stable" is used by '
                    'default.', type='choice', choices=browsers,
                    default='stable')
  parser.add_option('-v', '--verbose', help='Verbose logging.',
                    action='store_true')
  parser.add_option('-z', '--compress', help='Compress the resulting trace '
                    'with gzip. ', action='store_true')
  parser.add_option('-d', '--device', help='The Android device ID to use, '
                    'defaults to the value of ANDROID_SERIAL environment '
                    'variable. If not specified, only 0 or 1 connected '
                    'devices are supported.')

  # Add options from profile_chrome agents.
  for module in PROFILE_CHROME_AGENT_MODULES:
    parser.add_option_group(module.add_options(parser))

  return parser


def main():
  parser = _CreateOptionParser()
  options, _args = parser.parse_args()  # pylint: disable=unused-variable
  if options.trace_cc:
    parser.error("""--trace-cc is deprecated.

For basic jank busting uses, use  --trace-frame-viewer
For detailed study of ubercompositor, pass --trace-ubercompositor.

When in doubt, just try out --trace-frame-viewer.
""")

  if options.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  device = device_utils.DeviceUtils.HealthyDevices(device_arg=options.device)[0]
  package_info = profiler.GetSupportedBrowsers()[options.browser]

  if options.chrome_categories in ['list', 'help']:
    ui.PrintMessage('Collecting record categories list...', eol='')
    record_categories = []
    disabled_by_default_categories = []
    record_categories, disabled_by_default_categories = \
        chrome_tracing_agent.ChromeTracingAgent.GetCategories(
            device, package_info)

    ui.PrintMessage('done')
    ui.PrintMessage('Record Categories:')
    ui.PrintMessage('\n'.join('\t%s' % item \
        for item in sorted(record_categories)))

    ui.PrintMessage('\nDisabled by Default Categories:')
    ui.PrintMessage('\n'.join('\t%s' % item \
        for item in sorted(disabled_by_default_categories)))

    return 0

  if options.atrace_categories in ['list', 'help']:
    ui.PrintMessage('\n'.join(
        atrace_tracing_agent.AtraceAgent.GetCategories(device)))
    return 0

  if (perf_tracing_agent.PerfProfilerAgent.IsSupported() and
      options.perf_categories in ['list', 'help']):
    ui.PrintMessage('\n'.join(
        perf_tracing_agent.PerfProfilerAgent.GetCategories(device)))
    return 0

  if not options.time and not options.continuous:
    ui.PrintMessage('Time interval or continuous tracing should be specified.')
    return 1

  if options.chrome_categories and 'webview' in options.atrace_categories:
    logging.warning('Using the "webview" category in atrace together with '
                    'Chrome tracing results in duplicate trace events.')

  enabled_agents = []
  if options.chrome_categories:
    enabled_agents.append(
        chrome_tracing_agent.ChromeTracingAgent(device,
                                                package_info,
                                                options.ring_buffer,
                                                options.trace_memory))
  if options.atrace_categories:
    enabled_agents.append(
        atrace_tracing_agent.AtraceAgent(device,
                                         options.ring_buffer))

  if options.perf_categories:
    enabled_agents.append(
        perf_tracing_agent.PerfProfilerAgent(device))

  if options.ddms:
    enabled_agents.append(
        ddms_tracing_agent.DdmsAgent(device,
                                     package_info))

  if not enabled_agents:
    ui.PrintMessage('No trace categories enabled.')
    return 1

  if options.output:
    options.output = os.path.expanduser(options.output)
  result = profiler.CaptureProfile(
      options,
      enabled_agents,
      options.time if not options.continuous else 0,
      output=options.output,
      compress=options.compress,
      write_json=options.json)
  if options.view:
    if sys.platform == 'darwin':
      os.system('/usr/bin/open %s' % os.path.abspath(result))
    else:
      webbrowser.open(result)
