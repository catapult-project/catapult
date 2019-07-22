# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Builds the command line parser, processes args, and runs commands."""

import logging
import sys

from telemetry.command_line import commands
from telemetry.internal.util import binary_manager
from telemetry.internal.util import ps_util


DEFAULT_LOG_FORMAT = (
    '(%(levelname)s) %(asctime)s %(module)s.%(funcName)s:%(lineno)d  '
    '%(message)s')


def main(environment):
  # The log level is set in browser_options.
  # Clear the log handlers to ensure we can set up logging properly here.
  logging.getLogger().handlers = []
  logging.basicConfig(format=DEFAULT_LOG_FORMAT)

  ps_util.EnableListingStrayProcessesUponExitHook()

  # Get the command name from the command line.
  if len(sys.argv) > 1 and sys.argv[1] == '--help':
    sys.argv[1] = 'help'

  command_name = 'run'
  for arg in sys.argv[1:]:
    if not arg.startswith('-'):
      command_name = arg
      break

  # TODO(eakuefner): Remove this hack after we port to argparse.
  if command_name == 'help' and len(sys.argv) > 2 and sys.argv[2] == 'run':
    command_name = 'run'
    sys.argv[2] = '--help'

  # Validate and interpret the command name.
  matching_commands = commands.MatchingCommands(command_name)
  if len(matching_commands) > 1:
    print >> sys.stderr, (
        '"%s" is not a %s command. Did you mean one of these?' %
        (command_name, commands.ScriptName()))
    for command in matching_commands:
      print >> sys.stderr, '  %-10s %s' % (command.Name(),
                                           command.Description())
    return 1
  if matching_commands:
    command = matching_commands[0]
  else:
    command = commands.Run

  binary_manager.InitDependencyManager(environment.client_configs)

  # Parse and run the command.
  parser = command.CreateParser()
  command.AddCommandLineArgs(parser, environment)

  # Set the default chrome root variable.
  parser.set_defaults(chrome_root=environment.default_chrome_root)

  options, args = parser.parse_args()
  if matching_commands:
    args = args[1:]
  options.positional_args = args
  command.ProcessCommandLineArgs(parser, options, environment)

  return_code = command().Run(options)
  if return_code == -1:
    logging.warn('No stories were run.')
    return 0
  return return_code
