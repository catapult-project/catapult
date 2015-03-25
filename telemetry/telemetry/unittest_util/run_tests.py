# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys

from telemetry.core import browser_finder
from telemetry.core import browser_finder_exceptions
from telemetry.core import browser_options
from telemetry.core import command_line
from telemetry.core import device_finder
from telemetry.core import util
from telemetry import decorators
from telemetry.unittest_util import browser_test_case
from telemetry.unittest_util import options_for_unittests

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'third_party', 'typ')

import typ


class RunTestsCommand(command_line.OptparseCommand):
  """Run unit tests"""

  usage = '[test_name ...] [<options>]'

  def __init__(self):
    super(RunTestsCommand, self).__init__()
    self.stream = sys.stdout

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    options.browser_type = 'any'
    parser = options.CreateParser('%%prog %s' % cls.usage)
    return parser

  @classmethod
  def AddCommandLineArgs(cls, parser, _):
    parser.add_option('--repeat-count', type='int', default=1,
                      help='Repeats each a provided number of times.')
    parser.add_option('-d', '--also-run-disabled-tests',
                      dest='run_disabled_tests',
                      action='store_true', default=False,
                      help='Ignore @Disabled and @Enabled restrictions.')
    parser.add_option('--exact-test-filter', action='store_true', default=False,
                      help='Treat test filter as exact matches (default is '
                           'substring matches).')

    typ.ArgumentParser.add_option_group(parser,
                                        "Options for running the tests",
                                        running=True,
                                        skip=['-d', '-v', '--verbose'])
    typ.ArgumentParser.add_option_group(parser,
                                        "Options for reporting the results",
                                        reporting=True)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args, _):
    # We retry failures by default unless we're running a list of tests
    # explicitly.
    if not args.retry_limit and not args.positional_args:
      args.retry_limit = 3

    try:
      possible_browser = browser_finder.FindBrowser(args)
    except browser_finder_exceptions.BrowserFinderException, ex:
      parser.error(ex)

    if not possible_browser:
      parser.error('No browser found of type %s. Cannot run tests.\n'
                   'Re-run with --browser=list to see '
                   'available browser types.' % args.browser_type)

  @classmethod
  def main(cls, args=None, stream=None):  # pylint: disable=W0221
    # We override the superclass so that we can hook in the 'stream' arg.
    parser = cls.CreateParser()
    cls.AddCommandLineArgs(parser, None)
    options, positional_args = parser.parse_args(args)
    options.positional_args = positional_args
    cls.ProcessCommandLineArgs(parser, options, None)

    obj = cls()
    if stream is not None:
      obj.stream = stream
    return obj.Run(options)

  def Run(self, args):
    possible_browser = browser_finder.FindBrowser(args)

    runner = typ.Runner()
    if self.stream:
      runner.host.stdout = self.stream

    # Telemetry seems to overload the system if we run one test per core,
    # so we scale things back a fair amount. Many of the telemetry tests
    # are long-running, so there's a limit to how much parallelism we
    # can effectively use for now anyway.
    #
    # It should be possible to handle multiple devices if we adjust the
    # browser_finder code properly, but for now we only handle one on ChromeOS.
    if possible_browser.platform.GetOSName() == 'chromeos':
      runner.args.jobs = 1
    elif possible_browser.platform.GetOSName() == 'android':
      runner.args.jobs = len(device_finder.GetDevicesMatchingOptions(args))
      print 'Running tests with %d Android device(s).' % runner.args.jobs
    elif possible_browser.platform.GetOSVersionName() == 'xp':
      # For an undiagnosed reason, XP falls over with more parallelism.
      # See crbug.com/388256
      runner.args.jobs = max(int(args.jobs) // 4, 1)
    else:
      runner.args.jobs = max(int(args.jobs) // 2, 1)

    runner.args.metadata = args.metadata
    runner.args.passthrough = args.passthrough
    runner.args.path = args.path
    runner.args.retry_limit = args.retry_limit
    runner.args.test_results_server = args.test_results_server
    runner.args.test_type = args.test_type
    runner.args.timing = args.timing
    runner.args.top_level_dir = args.top_level_dir
    runner.args.verbose = args.verbosity
    runner.args.write_full_results_to = args.write_full_results_to
    runner.args.write_trace_to = args.write_trace_to

    runner.args.path.append(util.GetUnittestDataDir())

    runner.classifier = GetClassifier(args, possible_browser)
    runner.context = args
    runner.setup_fn = _SetUpProcess
    runner.teardown_fn = _TearDownProcess
    runner.win_multiprocessing = typ.WinMultiprocessing.importable
    try:
      ret, _, _ = runner.run()
    except KeyboardInterrupt:
      print >> sys.stderr, "interrupted, exiting"
      ret = 130
    return ret


def GetClassifier(args, possible_browser):
  def ClassifyTest(test_set, test):
    name = test.id()
    if (not args.positional_args
        or _MatchesSelectedTest(name, args.positional_args,
                                args.exact_test_filter)):
      assert hasattr(test, '_testMethodName')
      method = getattr(test, test._testMethodName) # pylint: disable=W0212
      should_skip, reason = decorators.ShouldSkip(method, possible_browser)
      if should_skip and not args.run_disabled_tests:
        test_set.tests_to_skip.append(typ.TestInput(name, msg=reason))
      elif decorators.ShouldBeIsolated(method, possible_browser):
        test_set.isolated_tests.append(typ.TestInput(name))
      else:
        test_set.parallel_tests.append(typ.TestInput(name))

  return ClassifyTest


def _MatchesSelectedTest(name, selected_tests, selected_tests_are_exact):
  if not selected_tests:
    return False
  if selected_tests_are_exact:
    return any(name in selected_tests)
  else:
    return any(test in name for test in selected_tests)


def _SetUpProcess(child, context): # pylint: disable=W0613
  args = context
  if args.device and args.device == 'android':
    android_devices = device_finder.GetDevicesMatchingOptions(args)
    args.device = android_devices[child.worker_num-1].guid
  options_for_unittests.Push(args)


def _TearDownProcess(child, context): # pylint: disable=W0613
  browser_test_case.teardown_browser()
  options_for_unittests.Pop()


if __name__ == '__main__':
  ret_code = RunTestsCommand.main()
  sys.exit(ret_code)
