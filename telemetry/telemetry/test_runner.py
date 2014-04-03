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

from telemetry import decorators
from telemetry import test
from telemetry.core import browser_options
from telemetry.core import command_line
from telemetry.core import discover
from telemetry.core import environment
from telemetry.core import util
from telemetry.page import page_set
from telemetry.page import page_test
from telemetry.page import profile_creator
from telemetry.util import find_dependencies


class Deps(find_dependencies.FindDependenciesCommand):
  """Prints all dependencies"""

  def Run(self, args):
    main_module = sys.modules['__main__']
    args.positional_args.append(os.path.realpath(main_module.__file__))
    return super(Deps, self).Run(args)


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
    if not args.positional_args:
      args.tests = _Tests()
    elif len(args.positional_args) == 1:
      args.tests = _MatchTestName(args.positional_args[0], exact_matches=False)
    else:
      parser.error('Must provide at most one test name.')

  def Run(self, args):
    if args.json:
      test_list = []
      for test_class in sorted(args.tests, key=lambda t: t.Name()):
        test_list.append({
            'name': test_class.Name(),
            'description': test_class.Description(),
            'options': test_class.options,
        })
      print json.dumps(test_list)
    else:
      _PrintTestList(args.tests)
    return 0


class Run(command_line.OptparseCommand):
  """Run one or more tests"""

  usage = 'test_name [page_set] [<options>]'

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('%%prog %s %s' % (cls.Name(), cls.usage))
    return parser

  @classmethod
  def AddCommandLineArgs(cls, parser):
    test.AddCommandLineArgs(parser)

    # Allow tests to add their own command line options.
    matching_tests = []
    for arg in sys.argv[1:]:
      matching_tests += _MatchTestName(arg)

    if matching_tests:
      # TODO(dtu): After move to argparse, add command-line args for all tests
      # to subparser. Using subparsers will avoid duplicate arguments.
      matching_test = matching_tests.pop()
      matching_test.AddCommandLineArgs(parser)
      # The test's options override the defaults!
      matching_test.SetArgumentDefaults(parser)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    if not args.positional_args:
      _PrintTestList(_Tests())
      sys.exit(-1)

    input_test_name = args.positional_args[0]
    matching_tests = _MatchTestName(input_test_name)
    if not matching_tests:
      print >> sys.stderr, 'No test named "%s".' % input_test_name
      print >> sys.stderr
      _PrintTestList(_Tests())
      sys.exit(-1)

    if len(matching_tests) > 1:
      print >> sys.stderr, 'Multiple tests named "%s".' % input_test_name
      print >> sys.stderr, 'Did you mean one of these?'
      print >> sys.stderr
      _PrintTestList(matching_tests)
      sys.exit(-1)

    test_class = matching_tests.pop()
    if issubclass(test_class, page_test.PageTest):
      if len(args.positional_args) < 2:
        parser.error('Need to specify a page set for "%s".' % test_class.Name())
      if len(args.positional_args) > 2:
        parser.error('Too many arguments.')
      page_set_path = args.positional_args[1]
      if not os.path.exists(page_set_path):
        parser.error('Page set not found.')
      if not (os.path.isfile(page_set_path) and
              discover.IsPageSetFile(page_set_path)):
        parser.error('Unsupported page set file format.')

      class TestWrapper(test.Test):
        test = test_class

        @classmethod
        def CreatePageSet(cls, options):
          return page_set.PageSet.FromFile(page_set_path)

      test_class = TestWrapper
    else:
      if len(args.positional_args) > 1:
        parser.error('Too many arguments.')

    assert issubclass(test_class, test.Test), 'Trying to run a non-Test?!'

    test_class.ProcessCommandLineArgs(parser, args)
    test.ProcessCommandLineArgs(parser, args)

    cls._test = test_class

  def Run(self, args):
    return min(255, self._test().Run(args))


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


@decorators.Cache
def _Tests():
  tests = []
  for base_dir in config.base_paths:
    tests += discover.DiscoverClasses(base_dir, base_dir, test.Test,
                                      index_by_class_name=True).values()
    page_tests = discover.DiscoverClasses(base_dir, base_dir,
                                          page_test.PageTest,
                                          index_by_class_name=True).values()
    tests += [test_class for test_class in page_tests
              if not issubclass(test_class, profile_creator.ProfileCreator)]
  return tests


def _MatchTestName(input_test_name, exact_matches=True):
  def _Matches(input_string, search_string):
    if search_string.startswith(input_string):
      return True
    for part in search_string.split('.'):
      if part.startswith(input_string):
        return True
    return False

  # Exact matching.
  if exact_matches:
    # Don't add aliases to search dict, only allow exact matching for them.
    if input_test_name in config.test_aliases:
      exact_match = config.test_aliases[input_test_name]
    else:
      exact_match = input_test_name

    for test_class in _Tests():
      if exact_match == test_class.Name():
        return [test_class]

  # Fuzzy matching.
  return [test_class for test_class in _Tests()
          if _Matches(input_test_name, test_class.Name())]


def _PrintTestList(tests):
  if not tests:
    print >> sys.stderr, 'No tests found!'
    return

  # Align the test names to the longest one.
  format_string = '  %%-%ds %%s' % max(len(t.Name()) for t in tests)

  filtered_tests = [test_class for test_class in tests
                    if issubclass(test_class, test.Test)]
  if filtered_tests:
    print >> sys.stderr, 'Available tests are:'
    for test_class in sorted(filtered_tests, key=lambda t: t.Name()):
      print >> sys.stderr, format_string % (
          test_class.Name(), test_class.Description())
    print >> sys.stderr

  filtered_tests = [test_class for test_class in tests
                    if issubclass(test_class, page_test.PageTest)]
  if filtered_tests:
    print >> sys.stderr, 'Available page tests are:'
    for test_class in sorted(filtered_tests, key=lambda t: t.Name()):
      print >> sys.stderr, format_string % (
          test_class.Name(), test_class.Description())
    print >> sys.stderr


config = environment.Environment([util.GetBaseDir()])


def main():
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
  options.positional_args = args
  command.ProcessCommandLineArgs(parser, options)
  return command().Run(options)
