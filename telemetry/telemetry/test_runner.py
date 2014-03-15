# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parses the command line, discovers the appropriate tests, and runs them.

Handles test configuration, but all the logic for
actually running the test is in Test and PageRunner."""

import inspect
import json
import os
import sys

from telemetry import test
from telemetry.core import browser_options
from telemetry.core import command_line
from telemetry.core import discover
from telemetry.core import util


class Help(command_line.OptparseCommand):
  """Display help information"""

  def Run(self, args):
    print >> sys.stderr, ('usage: %s <command> [<options>]' % _ScriptName())
    print >> sys.stderr, 'Available commands are:'
    for command in _Commands():
      print >> sys.stderr, '  %-10s %s' % (
          command.Name(), command.Description())
    return 0


class List(command_line.OptparseCommand):
  """Lists the available tests"""

  usage = '[test_name] [<options>]'

  @classmethod
  def AddCommandLineArgs(cls, parser):
    parser.add_option('-j', '--json', action='store_true')

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    if not args.tests:
      args.tests = _Tests()
    elif len(args.tests) == 1:
      args.tests = _MatchTestName(args.tests[0])
    else:
      parser.error('Must provide at most one test name.')

  def Run(self, args):
    if args.json:
      test_list = []
      for test_name, test_class in sorted(args.tests.items()):
        test_list.append({
              'name': test_name,
              'description': test_class.Description(),
              'options': test_class.options,
            })
      print json.dumps(test_list)
    else:
      print >> sys.stderr, 'Available tests are:'
      _PrintTestList(args.tests)
    return 0


class Run(command_line.OptparseCommand):
  """Run one or more tests"""

  usage = 'test_name [<options>]'

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('%%prog %s %s' % (cls.Name(), cls.usage))
    return parser

  @classmethod
  def AddCommandLineArgs(cls, parser):
    # Allow tests to add their own command line options.
    matching_tests = {}
    for arg in sys.argv[1:]:
      matching_tests.update(_MatchTestName(arg))
    # TODO(dtu): After move to argparse, add command-line args for all tests
    # to subparser. Using subparsers will avoid duplicate arguments.
    if matching_tests:
      matching_tests.values().pop().AddCommandLineArgs(parser)
    test.AddCommandLineArgs(parser)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    if len(args.tests) != 1:
      print >> sys.stderr, 'Available tests are:'
      _PrintTestList(_Tests())
      sys.exit(1)

    input_test_name = args.tests[0]
    matching_tests = _MatchTestName(input_test_name)
    if not matching_tests:
      print >> sys.stderr, 'No test named "%s".' % input_test_name
      print >> sys.stderr
      print >> sys.stderr, 'Available tests:'
      _PrintTestList(_Tests())
      sys.exit(1)
    if len(matching_tests) > 1:
      print >> sys.stderr, 'Multiple tests named "%s".' % input_test_name
      print >> sys.stderr
      print >> sys.stderr, 'Did you mean one of these?'
      _PrintTestList(matching_tests)
      sys.exit(1)

    args.test = matching_tests.popitem()[1]
    args.test.ProcessCommandLineArgs(parser, args)
    test.ProcessCommandLineArgs(parser, args)

  def Run(self, args):
    return min(255, args.test().Run(args))


def _ScriptName():
  return os.path.basename(sys.argv[0])


def _Commands():
  """Generates a list of all classes in this file that subclass Command."""
  for _, cls in inspect.getmembers(sys.modules[__name__]):
    if not inspect.isclass(cls):
      continue
    if not issubclass(cls, command_line.Command):
      continue
    yield cls


def _Tests():
  base_dir = util.GetBaseDir()
  tests = discover.DiscoverClasses(base_dir, base_dir, test.Test,
                                   index_by_class_name=True)
  return dict((test.Name(), test) for test in tests.itervalues())


def _MatchTestName(input_test_name):
  def _Matches(input_string, search_string):
    if search_string.startswith(input_string):
      return True
    for part in search_string.split('.'):
      if part.startswith(input_string):
        return True
    return False

  # Exact matching.
  if input_test_name in test_aliases:
    exact_match = test_aliases[input_test_name]
  else:
    exact_match = input_test_name
  if exact_match in _Tests():
    return {exact_match: _Tests()[exact_match]}

  # Fuzzy matching.
  return dict((test_name, test_class)
      for test_name, test_class in _Tests().iteritems()
      if _Matches(input_test_name, test_name))


def _PrintTestList(tests):
  for test_name, test_class in sorted(tests.items()):
    # Align the test names to the longest one.
    format_string = '  %%-%ds %%s' % max(map(len, tests.iterkeys()))
    print >> sys.stderr, format_string % (test_name, test_class.Description())


test_aliases = {}


def Main():
  # Get the command name from the command line.
  if len(sys.argv) > 1 and sys.argv[1] == '--help':
    sys.argv[1] = 'help'

  command_name = 'run'
  for arg in sys.argv[1:]:
    if not arg.startswith('-'):
      command_name = arg
      break

  # Validate and interpret the command name.
  commands = [command for command in _Commands()
              if command.Name().startswith(command_name)]
  if len(commands) > 1:
    print >> sys.stderr, ('"%s" is not a %s command. Did you mean one of these?'
                          % (command_name, _ScriptName()))
    for command in commands:
      print >> sys.stderr, '  %-10s %s' % (
          command.Name(), command.Description())
    return 1
  if commands:
    command = commands[0]
  else:
    command = Run

  # Parse and run the command.
  parser = command.CreateParser()
  command.AddCommandLineArgs(parser)
  options, args = parser.parse_args()
  if commands:
    args = args[1:]
  options.tests = args
  command.ProcessCommandLineArgs(parser, options)
  return command().Run(options)
