# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parses the command line, discovers the appropriate tests, and runs them.

Handles test configuration, but all the logic for
actually running the test is in Test and PageRunner."""

import copy
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

  def Run(self, options, args):
    print >> sys.stderr, ('usage: %s <command> [<options>]' % _GetScriptName())
    print >> sys.stderr, 'Available commands are:'
    for command in COMMANDS:
      print >> sys.stderr, '  %-10s %s' % (command.name, command.description)
    return 0


class List(command_line.OptparseCommand):
  """Lists the available tests"""

  usage = '[test_name] [<options>]'

  def __init__(self):
    super(List, self).__init__()
    self._tests = None

  def AddCommandLineOptions(self, parser):
    parser.add_option('-j', '--json', action='store_true')

  def ProcessCommandLine(self, parser, options, args):
    if not args:
      self._tests = _GetTests()
    elif len(args) == 1:
      self._tests = _MatchTestName(args[0])
    else:
      parser.error('Must provide at most one test name.')

  def Run(self, options, args):
    if options.json:
      test_list = []
      for test_name, test_class in sorted(self._tests.items()):
        test_list.append({
              'name': test_name,
              'description': test_class.__doc__,
              'options': test_class.options,
            })
      print json.dumps(test_list)
    else:
      print >> sys.stderr, 'Available tests are:'
      _PrintTestList(self._tests)
    return 0


class Run(command_line.OptparseCommand):
  """Run one or more tests"""

  usage = 'test_name [<options>]'

  def __init__(self):
    super(Run, self).__init__()
    self._test = None

  def CreateParser(self):
    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('%%prog %s %s' % (self.name, self.usage))
    return parser

  def AddCommandLineOptions(self, parser):
    test.Test.AddCommandLineOptions(parser)

    # Allow tests to add their own command line options.
    matching_tests = {}
    for arg in sys.argv[1:]:
      matching_tests.update(_MatchTestName(arg))
    for test_class in matching_tests.itervalues():
      test_class.AddTestCommandLineOptions(parser)

  def ProcessCommandLine(self, parser, options, args):
    if len(args) != 1:
      parser.error('Must provide one test name.')

    input_test_name = args[0]
    matching_tests = _MatchTestName(input_test_name)
    if not matching_tests:
      print >> sys.stderr, 'No test named "%s".' % input_test_name
      print >> sys.stderr
      print >> sys.stderr, 'Available tests:'
      _PrintTestList(_GetTests())
      sys.exit(1)
    if len(matching_tests) > 1:
      print >> sys.stderr, 'Multiple tests named "%s".' % input_test_name
      print >> sys.stderr
      print >> sys.stderr, 'Did you mean one of these?'
      _PrintTestList(matching_tests)
      sys.exit(1)

    self._test = matching_tests.popitem()[1]

  def Run(self, options, args):
    return min(255, self._test().Run(copy.copy(options)))


COMMANDS = [cls() for _, cls in inspect.getmembers(sys.modules[__name__])
            if inspect.isclass(cls)
            and cls is not command_line.OptparseCommand
            and issubclass(cls, command_line.OptparseCommand)]


def _GetScriptName():
  return os.path.basename(sys.argv[0])


def _GetTests():
  base_dir = util.GetBaseDir()
  tests = discover.DiscoverClasses(base_dir, base_dir, test.Test,
                                   index_by_class_name=True)
  return dict((test.GetName(), test) for test in tests.itervalues())


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
  if exact_match in _GetTests():
    return {exact_match: _GetTests()[exact_match]}

  # Fuzzy matching.
  return dict((test_name, test_class)
      for test_name, test_class in _GetTests().iteritems()
      if _Matches(input_test_name, test_name))


def _PrintTestList(tests):
  for test_name, test_class in sorted(tests.items()):
    if test_class.__doc__:
      description = test_class.__doc__.splitlines()[0]
      # Align the test names to the longest one.
      format_string = '  %%-%ds %%s' % max(map(len, tests.iterkeys()))
      print >> sys.stderr, format_string % (test_name, description)
    else:
      print >> sys.stderr, '  %s' % test_name


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
  commands = [command for command in COMMANDS
              if command.name.startswith(command_name)]
  if len(commands) > 1:
    print >> sys.stderr, ('"%s" is not a %s command. Did you mean one of these?'
                          % (command_name, _GetScriptName()))
    for command in commands:
      print >> sys.stderr, '  %-10s %s' % (command.name, command.description)
    return 1
  if commands:
    command = commands[0]
  else:
    command = Run()

  # Parse and run the command.
  parser = command.CreateParser()
  command.AddCommandLineOptions(parser)
  options, args = parser.parse_args()
  if commands:
    args = args[1:]
  command.ProcessCommandLine(parser, options, args)
  return command.Run(options, args)
