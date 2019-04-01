# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import itertools
import logging
import optparse
import os
import sys
import time

import py_utils
from py_utils import cloud_storage  # pylint: disable=import-error
from py_utils import memory_debug  # pylint: disable=import-error
from py_utils import logging_util  # pylint: disable=import-error

from telemetry.core import exceptions
from telemetry.internal.actions import page_action
from telemetry.internal.browser import browser_finder
from telemetry.internal.results import results_options
from telemetry.internal.util import exception_formatter
from telemetry import page
from telemetry.page import legacy_page_test
from telemetry import story as story_module
from telemetry.util import wpr_modes
from telemetry.web_perf import story_test
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


# Allowed stages to pause for user interaction at.
_PAUSE_STAGES = ('before-start-browser', 'after-start-browser',
                 'before-run-story', 'after-run-story')

_UNHANDLEABLE_ERRORS = (
    SystemExit,
    KeyboardInterrupt,
    ImportError,
    MemoryError,
    AttributeError,
    NameError)


class ArchiveError(Exception):
  pass


def AddCommandLineArgs(parser):
  story_module.StoryFilter.AddCommandLineArgs(parser)
  results_options.AddResultsOptions(parser)

  # Page set options
  group = optparse.OptionGroup(parser, 'Page set repeat options')
  # Note that the default for pageset-repeat is 1 unless the benchmark
  # specifies a different default by adding
  # `options = {'pageset_repeat': X}` in their benchmark. Defaults are always
  # overridden by passed in commandline arguments.
  group.add_option('--pageset-repeat', default=1, type='int',
                   help='Number of times to repeat the entire pageset. ')
  # TODO(crbug.com/910809): Add flag to reduce iterations to 1.
  # (An iteration is a repeat of the benchmark without restarting Chrome. It
  # must be supported in benchmark-specific code.) This supports the smoke
  # test use case since we don't want to waste time with iterations in smoke
  # tests.
  group.add_option('--max-failures', default=None, type='int',
                   help='Maximum number of test failures before aborting '
                   'the run. Defaults to the number specified by the '
                   'PageTest.')
  group.add_option('--pause', dest='pause', default=None,
                   choices=_PAUSE_STAGES,
                   help='Pause for interaction at the specified stage. '
                   'Valid stages are %s.' % ', '.join(_PAUSE_STAGES))
  parser.add_option_group(group)

  # WPR options
  group = optparse.OptionGroup(parser, 'Web Page Replay options')
  group.add_option(
      '--use-live-sites',
      dest='use_live_sites', action='store_true',
      help='Run against live sites and ignore the Web Page Replay archives.')
  parser.add_option_group(group)

  parser.add_option('-d', '--also-run-disabled-tests',
                    dest='run_disabled_tests',
                    action='store_true', default=False,
                    help='Ignore expectations.config disabling.')
  parser.add_option('-p', '--print-only', dest='print_only',
                    choices=['stories', 'tags', 'both'], default=None)

def ProcessCommandLineArgs(parser, args):
  story_module.StoryFilter.ProcessCommandLineArgs(parser, args)
  results_options.ProcessCommandLineArgs(args)

  if args.pageset_repeat < 1:
    parser.error('--pageset-repeat must be a positive integer.')


@contextlib.contextmanager
def CaptureLogsAsArtifacts(results, test_name):
  with results.CreateArtifact(test_name, 'logs') as log_file:
    with logging_util.CaptureLogs(log_file):
      yield


def _RunStoryAndProcessErrorIfNeeded(story, results, state, test):
  def ProcessError(exc, log_message):
    logging.exception(log_message)
    state.DumpStateUponFailure(story, results)

    # Dump app crash, if present
    if exc:
      if isinstance(exc, exceptions.AppCrashException):
        minidump_path = exc.minidump_path
        if minidump_path:
          results.AddArtifact(story.name, 'minidump', minidump_path)

    # Note: calling Fail on the results object also normally causes the
    # progress_reporter to log it in the output.
    results.Fail('Exception raised running %s' % story.name)

  with CaptureLogsAsArtifacts(results, story.name):
    try:
      if isinstance(test, story_test.StoryTest):
        test.WillRunStory(state.platform)
      state.WillRunStory(story)

      if not state.CanRunStory(story):
        results.Skip(
            'Skipped because story is not supported '
            '(SharedState.CanRunStory() returns False).')
        return
      story.wpr_mode = state.wpr_mode
      state.RunStory(results)
      if isinstance(test, story_test.StoryTest):
        test.Measure(state.platform, results)
    except page_action.PageActionNotSupported as exc:
      results.Skip('Unsupported page action: %s' % exc)
    except (legacy_page_test.Failure, exceptions.TimeoutException,
            exceptions.LoginException, py_utils.TimeoutException) as exc:
      ProcessError(exc, log_message='Handleable error')
    except _UNHANDLEABLE_ERRORS as exc:
      ProcessError(exc, log_message=('Unhandleable error. '
                                     'Benchmark run will be interrupted'))
      raise
    except Exception as exc:  # pylint: disable=broad-except
      ProcessError(exc, log_message=('Possibly handleable error. '
                                     'Will try to restart shared state'))
      # The caller (|Run| function) will catch this exception, destory and
      # create a new shared state.
      raise
    finally:
      has_existing_exception = (sys.exc_info() != (None, None, None))
      try:
        # We attempt to stop tracing and/or metric collecting before possibly
        # closing the browser. Closing the browser first and stopping tracing
        # later appeared to cause issues where subsequent browser instances
        # would not launch correctly on some devices (see: crbug.com/720317).
        # The following normally cause tracing and/or metric collecting to stop.
        if isinstance(test, story_test.StoryTest):
          test.DidRunStory(state.platform, results)
        else:
          test.DidRunPage(state.platform)
        # And the following normally causes the browser to be closed.
        state.DidRunStory(results)
      except Exception:  # pylint: disable=broad-except
        if not has_existing_exception:
          state.DumpStateUponFailure(story, results)
          raise
        # Print current exception and propagate existing exception.
        exception_formatter.PrintFormattedException(
            msg='Exception raised when cleaning story run: ')


def RunStorySet(test, story_set, possible_browser, expectations,
                browser_options, finder_options, results,
                max_failures=None, max_num_values=sys.maxint):
  """Runs a given test against a given page_set with the given options.

  Stop execution for unexpected exceptions such as KeyboardInterrupt.
  We "white list" certain exceptions for which the story runner
  can continue running the remaining stories.

  Args:
    test: a test to be run: either a StoryTest subclass for newer timeline
      based benchmarks, or a LegacyPageTest to support older benchmarks.
    story_set: an instance of StorySet, a collection of stories.
    possible_browser: an instance of PossibleBrowser.
    expectations: an instance of Expectations.
    browser_options: options to be passed to browser.
    finder_options: options controlling the execution of benchmark. This
      can be an instance of BrowserFinderOptions class, but only options
      relevant to benchmark execution will be read.
    max_failures: maximum allowed number of failures.
    max_num_values: maximum allowed number of values.
  """

  if (not finder_options.use_live_sites and
      browser_options.wpr_mode != wpr_modes.WPR_RECORD):
    # Get the serving dirs of the filtered stories.
    # TODO(crbug.com/883798): removing story_set._serving_dirs
    serving_dirs = story_set._serving_dirs.copy()
    for story in story_set:
      if story.serving_dir:
        serving_dirs.add(story.serving_dir)

    if story_set.bucket:
      for directory in serving_dirs:
        cloud_storage.GetFilesInDirectoryIfChanged(directory,
                                                   story_set.bucket)
    if story_set.archive_data_file and not _UpdateAndCheckArchives(
        story_set.archive_data_file, story_set.wpr_archive_info, story_set):
      return

  # Effective max failures gives priority to command-line flag value.
  effective_max_failures = finder_options.max_failures
  if effective_max_failures is None:
    effective_max_failures = max_failures

  state = None
  device_info_diags = {}
  # TODO(crbug.com/866458): unwind the nested blocks
  # pylint: disable=too-many-nested-blocks
  try:
    pageset_repeat = finder_options.pageset_repeat
    for storyset_repeat_counter in xrange(pageset_repeat):
      for story in story_set:
        start_timestamp = time.time()
        if not state:
          # Construct shared state by using a copy of finder_options. Shared
          # state may update the finder_options. If we tear down the shared
          # state after this story run, we want to construct the shared
          # state for the next story from the original finder_options.
          state = story_set.shared_state_class(
              test, finder_options.Copy(), story_set, possible_browser)

        results.WillRunPage(story, storyset_repeat_counter)
        story_run = results.current_page_run

        if expectations:
          disabled = expectations.IsStoryDisabled(
              story, state.platform, finder_options)
          if disabled:
            if finder_options.run_disabled_tests:
              logging.warning('Force running a disabled story: %s' %
                              story.name)
            else:
              results.Skip(disabled)
              results.DidRunPage(story)
              continue

        try:
          if state.platform:
            state.platform.WaitForBatteryTemperature(35)
            _WaitForThermalThrottlingIfNeeded(state.platform)
          _RunStoryAndProcessErrorIfNeeded(story, results, state, test)

          num_values = len(results.all_page_specific_values)
          # TODO(#4259): Convert this to an exception-based failure
          if num_values > max_num_values:
            msg = 'Too many values: %d > %d' % (num_values, max_num_values)
            logging.error(msg)
            results.Fail(msg)

          device_info_diags = _MakeDeviceInfoDiagnostics(state)
        except _UNHANDLEABLE_ERRORS:
          # Nothing else we should do for these. Re-raise the error.
          raise
        except Exception:  # pylint: disable=broad-except
          # For all other errors, try to give the rest of stories a chance
          # to run by tearing down the state and creating a new state instance
          # in the next iteration.
          try:
            # If TearDownState raises, do not catch the exception.
            # (The Error was saved as a failure value.)
            state.TearDownState()
          finally:
            # Later finally-blocks use state, so ensure it is cleared.
            state = None
        finally:
          has_existing_exception = sys.exc_info() != (None, None, None)
          try:
            if state and state.platform:
              _CheckThermalThrottling(state.platform)
            results.DidRunPage(story)
            story_run.SetDuration(time.time() - start_timestamp)
          except Exception:  # pylint: disable=broad-except
            if not has_existing_exception:
              raise
            # Print current exception and propagate existing exception.
            exception_formatter.PrintFormattedException(
                msg='Exception from result processing:')
        if (effective_max_failures is not None and
            results.num_failed > effective_max_failures):
          logging.error('Too many failures. Aborting.')
          return
  finally:
    results.ComputeTimelineBasedMetrics()
    results.PopulateHistogramSet()

    for name, diag in device_info_diags.iteritems():
      results.AddSharedDiagnosticToAllHistograms(name, diag)

    if state:
      has_existing_exception = sys.exc_info() != (None, None, None)
      try:
        state.TearDownState()
      except Exception: # pylint: disable=broad-except
        if not has_existing_exception:
          raise
        # Print current exception and propagate existing exception.
        exception_formatter.PrintFormattedException(
            msg='Exception from TearDownState:')


def _ValidateStory(story):
  if len(story.name) > 180:
    raise ValueError(
        'User story has name exceeding 180 characters: %s' %
        story.name)


def _PrintStories(story_set, finder_options):
  if finder_options.print_only == 'tags':
    tags = set(itertools.chain.from_iterable(s.tags for s in story_set))
    print 'List of tags:\n%s' % '\n'.join(tags)
    return 0
  include_tags = finder_options.print_only == 'both'
  if include_tags:
    format_string = '  %%-%ds %%s' % max(len(s.name) for s in story_set)
  else:
    format_string = '%s%s'
  for s in story_set:
    print format_string % (s.name, ','.join(s.tags) if include_tags else '')


def SetUpAndRunBenchmark(benchmark_to_run, finder_options):
  story_set, possible_browser, benchmark_enabled = _SetUpBenchmark(
      benchmark_to_run, finder_options)

  if finder_options.print_only:
    _PrintStories(story_set, finder_options)
    return 0

  if not benchmark_enabled:
    # If chartjson is specified, this will print a dict indicating the
    # benchmark name and disabled state.
    with results_options.CreateResults(
        benchmark_to_run.GetMetadata(), finder_options,
        should_add_value=benchmark_to_run.ShouldAddValue,
        benchmark_enabled=False
        ) as results:
      results.PrintSummary()
    # When a disabled benchmark is run we now want to return success since
    # we are no longer filtering these out in the buildbot recipes.
    return 0

  if not story_set:
    logging.warning('The specified filters did not match any stories.')
    return 0

  if not possible_browser:
    logging.error('No browser of type "%s" found for benchmark "%s"' % (
        finder_options.browser_options.browser_type, benchmark_to_run.Name()))
    return 0

  return RunBenchmark(
      benchmark_to_run, story_set, possible_browser,
      finder_options.browser_options, finder_options)


def _IsBenchmarkEnabled(benchmark_to_run, target_platform, finder_options):
  expectations = benchmark_to_run.expectations

  can_run_on_platform = benchmark_to_run._CanRunOnPlatform(
      target_platform, finder_options)
  expectations_disabled = expectations.IsBenchmarkDisabled(
      target_platform, finder_options)

  if expectations_disabled or not can_run_on_platform:
    print '%s is disabled on the selected browser' % benchmark_to_run.Name()
    if finder_options.run_disabled_tests and can_run_on_platform:
      print 'Running benchmark anyway due to: --also-run-disabled-tests'
    else:
      if can_run_on_platform:
        print 'Try --also-run-disabled-tests to force the benchmark to run.'
      else:
        print ("This platform is not supported for this benchmark. If this "
               "is in error please add it to the benchmark's supported "
               "platforms.")
      return False
  return True


def _SortedStorySet(story_set):
  """ Returns a story set with stories sorted by the archive name.
  """
  wpr_archive_info = story_set.wpr_archive_info
  if wpr_archive_info:
    stories = sorted(story_set.stories,
                     key=wpr_archive_info.WprFilePathForStory)
    story_set = story_module.story_set.StorySet(
        archive_data_file=story_set.archive_data_file,
        cloud_storage_bucket=story_set.bucket,
        base_dir=story_set.base_dir,
        serving_dirs=story_set.serving_dirs,
    )
    for story in stories:
      story_set.AddStory(story)
  return story_set


def _SetUpBenchmark(benchmark_to_run, finder_options):
  benchmark_to_run.CustomizeOptions(finder_options)

  finder_options.target_platforms = benchmark_to_run.GetSupportedPlatformNames(
      benchmark_to_run.SUPPORTED_PLATFORMS)
  possible_browser = browser_finder.FindBrowser(finder_options)

  benchmark_enabled = _IsBenchmarkEnabled(
      benchmark_to_run, possible_browser.platform, finder_options)

  story_set = benchmark_to_run.CreateStorySet(finder_options)
  for s in story_set:
    _ValidateStory(s)

  # We want to make sure that all expectations are linked to real stories,
  # this will log error messages if names do not match what is in the set.
  benchmark_to_run.GetBrokenExpectations(story_set)

  # Filter page set based on options.
  story_set = story_module.StoryFilter.FilterStorySet(story_set)

  # Sort stories to minimize how often the network replay-server
  # needs to be restarted.
  story_set = _SortedStorySet(story_set)

  return (story_set, possible_browser, benchmark_enabled)


def RunBenchmark(benchmark, story_set, possible_browser,
                 browser_options, finder_options):
  """Run the benchmark on the given browser with given options.

  Args:
    benchmark: an instance of Benchmark class, a benchmark to be run.
    story_set: and instance of StorySet, a collection of stories.
    possible_browser: an instance of PossibleBrowser.
    browser_options: options to be passed to browser.
    finder_options: options controlling the execution of benchmark. This
      can be an instance of BrowserFinderOptions class, but only options
      relevant to benchmark execution will be read.

  Returns:
    1 if there is failure or 2 if there is an uncaught exception.
  """
  benchmark_metadata = benchmark.GetMetadata()
  page_test = benchmark.CreatePageTest(finder_options)
  page_test.__name__ = benchmark.__class__.__name__

  if isinstance(page_test, legacy_page_test.LegacyPageTest):
    if any(not isinstance(p, page.Page) for p in story_set):
      raise Exception(
          'PageTest must be used with StorySet containing only '
          'telemetry.page.Page stories.')

  with results_options.CreateResults(
      benchmark_metadata, finder_options,
      should_add_value=benchmark.ShouldAddValue,
      benchmark_enabled=True) as results:
    try:
      RunStorySet(
          page_test, story_set, possible_browser,
          benchmark.expectations, browser_options, finder_options, results,
          benchmark.max_failures, benchmark.MAX_NUM_VALUES)
      return_code = 1 if results.had_failures else 0
    except Exception as e: # pylint: disable=broad-except
      logging.fatal(
          'Benchmark execution interrupted by a fatal exception: %s(%s)' %
          (type(e), e))
      results.InterruptBenchmark(story_set, finder_options.pageset_repeat)
      exception_formatter.PrintFormattedException()
      return_code = 2

    benchmark_owners = benchmark.GetOwners()
    benchmark_component = benchmark.GetBugComponents()
    benchmark_documentation_url = benchmark.GetDocumentationLink()

    if benchmark_owners:
      results.AddSharedDiagnosticToAllHistograms(
          reserved_infos.OWNERS.name, benchmark_owners)

    if benchmark_component:
      results.AddSharedDiagnosticToAllHistograms(
          reserved_infos.BUG_COMPONENTS.name, benchmark_component)

    if benchmark_documentation_url:
      results.AddSharedDiagnosticToAllHistograms(
          reserved_infos.DOCUMENTATION_URLS.name, benchmark_documentation_url)

    try:
      if finder_options.upload_results:
        results.UploadTraceFilesToCloud()
        results.UploadArtifactsToCloud()
    finally:
      memory_debug.LogHostMemoryUsage()
      results.PrintSummary()
  return return_code


def _UpdateAndCheckArchives(archive_data_file, wpr_archive_info,
                            filtered_stories):
  """Verifies that all stories are local or have WPR archives.

  Logs warnings and returns False if any are missing.
  """
  # Report any problems with the entire story set.
  story_names = [s.name for s in filtered_stories if not s.is_local]
  if story_names:
    if not archive_data_file:
      logging.error('The story set is missing an "archive_data_file" '
                    'property.\nTo run from live sites pass the flag '
                    '--use-live-sites.\nTo create an archive file add an '
                    'archive_data_file property to the story set and then '
                    'run record_wpr.')
      raise ArchiveError('No archive data file.')
    if not wpr_archive_info:
      logging.error('The archive info file is missing.\n'
                    'To fix this, either add svn-internal to your '
                    '.gclient using http://goto/read-src-internal, '
                    'or create a new archive using record_wpr.')
      raise ArchiveError('No archive info file.')
    wpr_archive_info.DownloadArchivesIfNeeded(story_names=story_names)

  # Report any problems with individual story.
  stories_missing_archive_path = []
  stories_missing_archive_data = []
  for story in filtered_stories:
    if not story.is_local:
      archive_path = wpr_archive_info.WprFilePathForStory(story)
      if not archive_path:
        stories_missing_archive_path.append(story)
      elif not os.path.isfile(archive_path):
        stories_missing_archive_data.append(story)
  if stories_missing_archive_path:
    logging.error(
        'The story set archives for some stories do not exist.\n'
        'To fix this, record those stories using record_wpr.\n'
        'To ignore this warning and run against live sites, '
        'pass the flag --use-live-sites.')
    logging.error(
        'stories without archives: %s',
        ', '.join(story.name
                  for story in stories_missing_archive_path))
  if stories_missing_archive_data:
    logging.error(
        'The story set archives for some stories are missing.\n'
        'Someone forgot to check them in, uploaded them to the '
        'wrong cloud storage bucket, or they were deleted.\n'
        'To fix this, record those stories using record_wpr.\n'
        'To ignore this warning and run against live sites, '
        'pass the flag --use-live-sites.')
    logging.error(
        'stories missing archives: %s',
        ', '.join(story.name
                  for story in stories_missing_archive_data))
  if stories_missing_archive_path or stories_missing_archive_data:
    raise ArchiveError('Archive file is missing stories.')
  # Only run valid stories if no problems with the story set or
  # individual stories.
  return True


def _WaitForThermalThrottlingIfNeeded(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  thermal_throttling_retry = 0
  while (platform.IsThermallyThrottled() and
         thermal_throttling_retry < 3):
    logging.warning('Thermally throttled, waiting (%d)...',
                    thermal_throttling_retry)
    thermal_throttling_retry += 1
    time.sleep(thermal_throttling_retry * 2)

  if thermal_throttling_retry and platform.IsThermallyThrottled():
    logging.warning('Device is thermally throttled before running '
                    'performance tests, results will vary.')


def _CheckThermalThrottling(platform):
  if not platform.CanMonitorThermalThrottling():
    return
  if platform.HasBeenThermallyThrottled():
    logging.warning('Device has been thermally throttled during '
                    'performance tests, results will vary.')

def _MakeDeviceInfoDiagnostics(state):
  if not state or not state.platform:
    return {}

  device_info_data = {
      reserved_infos.ARCHITECTURES.name: state.platform.GetArchName(),
      reserved_infos.DEVICE_IDS.name: state.platform.GetDeviceId(),
      # This is not consistent and caused dashboard upload failure
      # TODO(crbug.com/854676): reenable this later if this is proved to be
      # useful
      # reserved_infos.MEMORY_AMOUNTS.name:
      #    state.platform.GetSystemTotalPhysicalMemory(),
      reserved_infos.OS_NAMES.name: state.platform.GetOSName(),
      reserved_infos.OS_VERSIONS.name: state.platform.GetOSVersionName(),
  }

  device_info_diangostics = {}

  for name, value in device_info_data.iteritems():
    if not value:
      continue
    device_info_diangostics[name] = generic_set.GenericSet([value])
  return device_info_diangostics
