# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Builds the command line parser, processes args, and runs commands."""

import argparse
import logging
import sys

from telemetry.command_line import commands
from telemetry.internal.util import binary_manager
from telemetry.internal.util import ps_util


DEFAULT_LOG_FORMAT = (
    '(%(levelname)s) %(asctime)s %(module)s.%(funcName)s:%(lineno)d  '
    '%(message)s')


_COMMANDS = {
    'run': commands.Run,
    'list': commands.List,
}


def ArgumentParser(results_arg_parser=None):
  """Build the top level argument parser.

  Currently this only defines two (mostly) empty parsers for 'run' and 'list'
  commands. After the selected command is parsed from the command line,
  remaining unknown args may be passed to the respective legacy opt_parser of
  the chosen command.

  TODO(crbug.com/981349): Other options should be migrated away from optparse
  and registered here instead using the corresponding argparse methods.

  Args:
    results_arg_parser: An optional parser defining extra command line options
      for an external results_processor. These are appended to the options of
      the 'run' command.
  Returns:
    An argparse.ArgumentParser object.
  """
  parser = argparse.ArgumentParser(
      description='Command line tool to run performance benchmarks.',
      epilog='To get help about a command use e.g.: %(prog)s run --help')
  subparsers = parser.add_subparsers(dest='command', title='commands')
  subparsers.required = True

  subparsers.add_parser(
      'run',
      help='run a benchmark (default)',
      description='Run a benchmark.',
      parents=[results_arg_parser] if results_arg_parser else [],
      add_help=False)

  subparsers.add_parser(
      'list',
      help='list benchmarks or stories',
      description='List available benchmarks or stories.',
      add_help=False)

  return parser


def ParseArgs(environment, args=None, results_arg_parser=None):
  """Parse command line arguments.

  Args:
    environment: A ProjectConfig object with information about the benchmark
      runtime environment.
    args: An optional list of arguments to parse. Defaults to obtain the
      arguments from sys.argv.
    results_arg_parser: An optional parser defining extra command line options
      for an external results_processor.

  Returns:
    An options object with the values parsed from the command line.
  """
  if args is None:
    args = sys.argv[1:]
  if len(args) > 0:
    if args[0] == 'help':
      # The old command line allowed "help" as a command. Now just translate
      # to "--help" to teach users about the new interface.
      args[0] = '--help'
    elif args[0] not in ['list', 'run', '-h', '--help']:
      args.insert(0, 'run')  # Default command.

  # TODO(crbug.com/981349): When optparse is gone, this should just call
  # parse_args on the fully formed parser as returned by.ArgumentParser.
  # For now we still need allow unknown args, which are then passed below to
  # the legacy parsers.
  parser = ArgumentParser(results_arg_parser)
  parsed_args, unknown = parser.parse_known_args(args)

  # TODO(crbug.com/981349): Ideally, most of the following should be moved
  # to after argument parsing is completed and before (or at the time) when
  # arguments are processed.

  # The log level is set in browser_options.
  # Clear the log handlers to ensure we can set up logging properly here.
  logging.getLogger().handlers = []
  logging.basicConfig(format=DEFAULT_LOG_FORMAT)

  binary_manager.InitDependencyManager(environment.client_configs)

  command = _COMMANDS[parsed_args.command]
  opt_parser = command.CreateParser()
  command.AddCommandLineArgs(opt_parser, environment)

  # Set the default chrome root variable.
  opt_parser.set_defaults(chrome_root=environment.default_chrome_root)

  options, positional_args = opt_parser.parse_args(unknown)
  options.positional_args = positional_args
  command.ProcessCommandLineArgs(opt_parser, options, environment)

  # Merge back our argparse args with the optparse options.
  for arg in vars(parsed_args):
    setattr(options, arg, getattr(parsed_args, arg))
  return options


def RunCommand(options):
  """Run a selected command from parsed command line args.

  Args:
    options: The return value from ParseArgs.

  Returns:
    The exit_code from the command execution.
  """
  ps_util.EnableListingStrayProcessesUponExitHook()
  return_code = _COMMANDS[options.command]().Run(options)
  if return_code == -1:
    logging.warning('No stories were run.')
    return 0
  return return_code


def main(environment):
  """Parse command line arguments and immediately run the selected command."""
  options = ParseArgs(environment)
  return RunCommand(options)
