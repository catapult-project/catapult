#!/usr/bin/env python

# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Android system-wide tracing utility.

This is a tool for capturing a trace that includes data from both userland and
the kernel.  It creates an HTML file for visualizing the trace.
"""

import sys

# Make sure we're using a new enough version of Python.
# The flags= parameter of re.sub() is new in Python 2.7. And Systrace does not
# support Python 3 yet.
version = sys.version_info[:2]
if version != (2, 7):
  sys.stderr.write('This script does not support Python %d.%d. '
                   'Please use Python 2.7.\n' % version)
  sys.exit(1)

import imp
import optparse
import os


# The default agent directory.
DEFAULT_AGENT_DIR = 'agents'


def parse_options(argv):
  """Parses and checks the command-line options.

  Returns:
    A tuple containing the options structure and a list of categories to
    be traced.
  """
  usage = 'Usage: %prog [options] [category1 [category2 ...]]'
  desc = 'Example: %prog -b 32768 -t 15 gfx input view sched freq'
  parser = optparse.OptionParser(usage=usage, description=desc)
  parser.add_option('-o', dest='output_file', help='write HTML to FILE',
                    default='trace.html', metavar='FILE')
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
  parser.add_option('--link-assets', dest='link_assets', default=False,
                    action='store_true',
                    help='(deprecated)')
  parser.add_option('--boot', dest='boot', default=False, action='store_true',
                    help='reboot the device with tracing during boot enabled. '
                    'The report is created by hitting Ctrl+C after the device '
                    'has booted up.')
  parser.add_option('--from-file', dest='from_file', action='store',
                    help='read the trace from a file (compressed) rather than '
                    'running a live trace')
  parser.add_option('--asset-dir', dest='asset_dir', default='trace-viewer',
                    type='string', help='(deprecated)')
  parser.add_option('-e', '--serial', dest='device_serial', type='string',
                    help='adb device serial number')
  parser.add_option('--agent-dirs', dest='agent_dirs', type='string',
                    help='the directories of additional systrace agent modules.'
                    ' The directories should be comma separated, e.g., '
                    '--agent-dirs=dir1,dir2,dir3. Directory |%s| is the default'
                    ' agent directory and will always be checked.'
                    % DEFAULT_AGENT_DIR)
  parser.add_option('--target', dest='target', default='android', type='string',
                    help='chose tracing target (android or linux)')

  options, categories = parser.parse_args(argv[1:])

  if options.link_assets or options.asset_dir != 'trace-viewer':
    parser.error('--link-assets and --asset-dir are deprecated.')

  if (options.trace_time is not None) and (options.trace_time <= 0):
    parser.error('the trace time must be a positive number')

  if (options.trace_buf_size is not None) and (options.trace_buf_size <= 0):
    parser.error('the trace buffer size must be a positive number')

  return (options, categories)


def write_trace_html(html_filename, script_dir, agents):
  """Writes out a trace html file.

  Args:
    html_filename: The name of the file to write.
    script_dir: The directory containing this script.
    agents: The systrace agents.
  """
  systrace_dir = os.path.abspath(os.path.dirname(__file__))
  html_prefix = read_asset(systrace_dir, 'prefix.html')
  html_suffix = read_asset(systrace_dir, 'suffix.html')
  trace_viewer_html = read_asset(script_dir, 'systrace_trace_viewer.html')

  # Open the file in binary mode to prevent python from changing the
  # line endings.
  html_file = open(html_filename, 'wb')
  html_file.write(html_prefix.replace('{{SYSTRACE_TRACE_VIEWER_HTML}}',
                                      trace_viewer_html))

  html_file.write('<!-- BEGIN TRACE -->\n')
  for a in agents:
    html_file.write('  <script class="')
    html_file.write(a.get_class_name())
    html_file.write('" type="application/text">\n')
    html_file.write(a.get_trace_data())
    html_file.write('  </script>\n')
  html_file.write('<!-- END TRACE -->\n')

  html_file.write(html_suffix)
  html_file.close()
  print '\n    wrote file://%s\n' % os.path.abspath(html_filename)


def create_agents(options, categories):
  """Create systrace agents.

  This function will search systrace agent modules in agent directories and
  create the corresponding systrace agents.
  Args:
    options: The command-line options.
    categories: The trace categories to capture.
  Returns:
    The list of systrace agents.
  """
  agent_dirs = [os.path.join(os.path.dirname(__file__), DEFAULT_AGENT_DIR)]
  if options.agent_dirs:
    agent_dirs.extend(options.agent_dirs.split(','))

  agents = []
  for agent_dir in agent_dirs:
    if not agent_dir:
      continue
    for filename in os.listdir(agent_dir):
      (module_name, ext) = os.path.splitext(filename)
      if (ext != '.py' or module_name == '__init__'
          or module_name.endswith('_unittest')):
        continue
      (f, pathname, data) = imp.find_module(module_name, [agent_dir])
      try:
        module = imp.load_module(module_name, f, pathname, data)
      finally:
        if f:
          f.close()
      if module:
        agent = module.try_create_agent(options, categories)
        if not agent:
          continue
        agents.append(agent)
  return agents


def main():
  options, categories = parse_options(sys.argv)
  agents = create_agents(options, categories)

  if not agents:
    dirs = DEFAULT_AGENT_DIR
    if options.agent_dirs:
      dirs += ',' + options.agent_dirs
    sys.stderr.write('No systrace agent is available in directories |%s|.\n' %
                     dirs)
    sys.exit(1)

  try:
    from . import update_systrace_trace_viewer
  except ImportError:
    pass
  else:
    update_systrace_trace_viewer.update()

  for a in agents:
    a.start()

  for a in agents:
    a.collect_result()
    if not a.expect_trace():
      # Nothing more to do.
      return

  script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
  write_trace_html(options.output_file, script_dir, agents)


def read_asset(src_dir, filename):
  return open(os.path.join(src_dir, filename)).read()


if __name__ == '__main__' and __package__ is None:
  # Add current package to search path.
  _SYSTRACE_DIR = os.path.abspath(
      os.path.join(os.path.dirname(__file__), os.path.pardir))
  sys.path.insert(0, _SYSTRACE_DIR)
  __package__ = "systrace"  # pylint: disable=redefined-builtin

  main()
