#!/usr/bin/env python

# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Android system-wide tracing utility.

This is a tool for capturing a trace that includes data from both userland and
the kernel.  It creates an HTML file for visualizing the trace.
"""

# Make sure we're using a new enough version of Python.
# The flags= parameter of re.sub() is new in Python 2.7. And Systrace does not
# support Python 3 yet.

import sys

version = sys.version_info[:2]
if version != (2, 7):
  sys.stderr.write('This script does not support Python %d.%d. '
                   'Please use Python 2.7.\n' % version)
  sys.exit(1)


import optparse
import os
import time

_SYSTRACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.pardir))
_CATAPULT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.path.pardir, os.path.pardir)
_DEVIL_DIR = os.path.join(_CATAPULT_DIR, 'devil')
if _DEVIL_DIR not in sys.path:
  sys.path.insert(0, _DEVIL_DIR)
if _SYSTRACE_DIR not in sys.path:
  sys.path.insert(0, _SYSTRACE_DIR)

from devil.utils import cmd_helper
from systrace import systrace_runner
from systrace.tracing_agents import atrace_agent
from systrace.tracing_agents import ftrace_agent


def parse_options(argv):
  """Parses and checks the command-line options.

  Returns:
    A tuple containing the options structure and a list of categories to
    be traced.
  """
  usage = 'Usage: %prog [options] [category1 [category2 ...]]'
  desc = 'Example: %prog -b 32768 -t 15 gfx input view sched freq'
  parser = optparse.OptionParser(usage=usage, description=desc)
  parser.add_option('-o', dest='output_file', help='write trace output to FILE',
                    default=None, metavar='FILE')
  parser.add_option('-t', '--time', dest='trace_time', type='int',
                    help='trace for N seconds', metavar='N')
  parser.add_option('-b', '--buf-size', dest='trace_buf_size', type='int',
                    help='use a trace buffer size of N KB', metavar='N')
  parser.add_option('-k', '--ktrace', dest='kfuncs', action='store',
                    help='specify a comma-separated list of kernel functions '
                    'to trace')
  parser.add_option('-l', '--list-categories', dest='list_categories',
                    default=False, action='store_true',
                    help='list the available categories and exit')
  parser.add_option('-j', '--json', dest='write_json',
                    default=False, action='store_true',
                    help='write a JSON file')
  parser.add_option('-a', '--app', dest='app_name', default=None, type='string',
                    action='store',
                    help='enable application-level tracing for comma-separated '
                    'list of app cmdlines')
  parser.add_option('--no-fix-threads', dest='fix_threads', default=True,
                    action='store_false',
                    help='don\'t fix missing or truncated thread names')
  parser.add_option('--no-fix-tgids', dest='fix_tgids', default=True,
                    action='store_false',
                    help='Do not run extra commands to restore missing thread '
                    'to thread group id mappings.')
  parser.add_option('--no-fix-circular', dest='fix_circular', default=True,
                    action='store_false',
                    help='don\'t fix truncated circular traces')
  parser.add_option('--no-compress', dest='compress_trace_data',
                    default=True, action='store_false',
                    help='Tell the device not to send the trace data in '
                    'compressed form.')
  parser.add_option('--hubs', dest='hub_types', default='plugable_7port',
                    help='List of hub types to check for for BattOr mapping. '
                    'Used when updating mapping file.')
  parser.add_option('--serial-map', dest='serial_map',
                    default='serial_map.json',
                    help='File containing pregenerated map of phone serial '
                    'numbers to BattOr serial numbers.')
  parser.add_option('--battor_path', dest='battor_path', default=None,
                    type='string', help='specify a BattOr path to use')
  parser.add_option('--update-map', dest='update_map', default=False,
                    action='store_true',
                    help='force update of phone-to-BattOr map')
  parser.add_option('--link-assets', dest='link_assets', default=False,
                    action='store_true',
                    help='(deprecated)')
  parser.add_option('--boot', dest='boot', default=False, action='store_true',
                    help='reboot the device with tracing during boot enabled. '
                    'The report is created by hitting Ctrl+C after the device '
                    'has booted up.')
  parser.add_option('--battor', dest='battor', default=False,
                    action='store_true', help='Use the BattOr tracing agent.')
  parser.add_option('--from-file', dest='from_file', action='store',
                    help='read the trace from a file (compressed) rather than '
                    'running a live trace')
  parser.add_option('--asset-dir', dest='asset_dir', default='trace-viewer',
                    type='string', help='(deprecated)')
  parser.add_option('-e', '--serial', dest='device_serial_number',
                    type='string', help='adb device serial number')
  parser.add_option('--target', dest='target', default='android', type='string',
                    help='chose tracing target (android or linux)')
  parser.add_option('--timeout', dest='timeout', type='int',
                    help='timeout for start and stop tracing (seconds)')
  parser.add_option('--collection-timeout', dest='collection_timeout',
                    type='int', help='timeout for data collection (seconds)')

  options, categories = parser.parse_args(argv[1:])

  if options.output_file is None:
    options.output_file = 'trace.json' if options.write_json else 'trace.html'

  if options.link_assets or options.asset_dir != 'trace-viewer':
    parser.error('--link-assets and --asset-dir are deprecated.')

  if options.trace_time and options.trace_time < 0:
    parser.error('the trace time must be a non-negative number')

  if (options.trace_buf_size is not None) and (options.trace_buf_size <= 0):
    parser.error('the trace buffer size must be a positive number')

  return (options, categories)

def get_device_serials():
  """Get the serial numbers of devices connected via adb.

  Only gets serial numbers of "active" devices (e.g. does not get serial
  numbers of devices which have not been authorized.)
  """
  cmdout = cmd_helper.GetCmdOutput(['adb', 'devices'])
  lines = [x.split() for x in cmdout.splitlines()[1:-1]]
  return [x[0] for x in lines if x[1] == 'device']

def main():
  # Parse the command line options.
  options, categories = parse_options(sys.argv)

  if options.target == 'android' and not options.device_serial_number:
    devices = get_device_serials()
    if len(devices) == 0:
      raise RuntimeError('No ADB devices connected.')
    elif len(devices) >= 2:
      raise RuntimeError('Multiple devices connected, serial number required')
    options.device_serial_number = devices[0]

  # If list_categories is selected, just print the list of categories.
  # In this case, use of the tracing controller is not necessary.
  if options.list_categories:
    if options.target == 'android':
      atrace_agent.list_categories(options)
    elif options.target == 'linux':
      ftrace_agent.list_categories(options)
    return

  # Set up the systrace runner and start tracing.
  script_dir = os.path.dirname(os.path.abspath(__file__))
  controller = systrace_runner.SystraceRunner(
      script_dir, options, categories)
  controller.StartTracing()

  # Wait for the given number of seconds or until the user presses enter.
  # pylint: disable=superfluous-parens
  # (need the parens so no syntax error if trying to load with Python 3)
  if options.from_file is not None:
    print('Reading results from file.')
  elif options.trace_time:
    print('Starting tracing (%d seconds)' % options.trace_time)
    time.sleep(options.trace_time)
  else:
    raw_input('Starting tracing (stop with enter)')

  # Stop tracing and collect the output.
  print('Tracing completed. Collecting output...')
  controller.StopTracing()
  print('Outputting Systrace results...')
  controller.OutputSystraceResults(write_json=options.write_json)

if __name__ == '__main__' and __package__ is None:
  main()
