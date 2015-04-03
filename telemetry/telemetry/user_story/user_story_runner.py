#  Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import optparse
import os
import random
import sys
import time

from telemetry.core import exceptions
from telemetry.core import wpr_modes
from telemetry.internal.actions import page_action
from telemetry import page as page_module
from telemetry.page import page_set as page_set_module
from telemetry.page import page_test
from telemetry.results import results_options
from telemetry.user_story import user_story_filter
from telemetry.user_story import user_story_set as user_story_set_module
from telemetry.util import cloud_storage
from telemetry.util import exception_formatter
from telemetry.value import failure
from telemetry.value import skip


class ArchiveError(Exception):
  pass


def AddCommandLineArgs(parser):
  user_story_filter.UserStoryFilter.AddCommandLineArgs(parser)
  results_options.AddResultsOptions(parser)

  # Page set options
  group = optparse.OptionGroup(parser, 'Page set repeat options')
  group.add_option('--page-repeat', default=1, type='int',
                   help='Number of times to repeat each individual page '
                   'before proceeding with the next page in the pageset.')
  group.add_option('--pageset-repeat', default=1, type='int',
                   help='Number of times to repeat the entire pageset.')
  group.add_option('--max-failures', default=None, type='int',
                   help='Maximum number of test failures before aborting '
                   'the run. Defaults to the number specified by the '
                   'PageTest.')
  parser.add_option_group(group)

  # WPR options
  group = optparse.OptionGroup(parser, 'Web Page Replay options')
  group.add_option('--use-live-sites',
      dest='use_live_sites', action='store_true',
      help='Run against live sites and ignore the Web Page Replay archives.')
  parser.add_option_group(group)

  parser.add_option('-d', '--also-run-disabled-tests',
                    dest='run_disabled_tests',
                    action='store_true', default=False,
                    help='Ignore @Disabled and @Enabled restrictions.')

def ProcessCommandLineArgs(parser, args):
  user_story_filter.UserStoryFilter.ProcessCommandLineArgs(parser, args)
  results_options.ProcessCommandLineArgs(parser, args)

  # Page set options
  if args.page_repeat < 1:
    parser.error('--page-repeat must be a positive integer.')
  if args.pageset_repeat < 1:
    parser.error('--pageset-repeat must be a positive integer.')


def _RunUserStoryAndProcessErrorIfNeeded(expectations, user_story, results,
                                         state):
  def ProcessError():
    if expectation == 'fail':
      msg = 'Expected exception while running %s' % user_story.display_name
      exception_formatter.PrintFormattedException(msg=msg)
    else:
      msg = 'Exception while running %s' % user_story.display_name
      results.AddValue(failure.FailureValue(user_story, sys.exc_info()))
  try:
    expectation = None
    state.WillRunUserStory(user_story)
    expectation, skip_value = state.GetTestExpectationAndSkipValue(expectations)
    if expectation == 'skip':
      assert skip_value
      results.AddValue(skip_value)
      return
    state.RunUserStory(results)
  except (page_test.Failure, exceptions.TimeoutException,
          exceptions.LoginException, exceptions.ProfilingException):
    ProcessError()
  except exceptions.Error:
    ProcessError()
    raise
  except page_action.PageActionNotSupported as e:
    results.AddValue(
        skip.SkipValue(user_story, 'Unsupported page action: %s' % e))
  except Exception:
    results.AddValue(
        failure.FailureValue(
            user_story, sys.exc_info(), 'Unhandlable exception raised.'))
    raise
  else:
    if expectation == 'fail':
      logging.warning(
          '%s was expected to fail, but passed.\n', user_story.display_name)
  finally:
    has_existing_exception = sys.exc_info() is not None
    try:
      state.DidRunUserStory(results)
    except Exception:
      if not has_existing_exception:
        raise
      # Print current exception and propagate existing exception.
      exception_formatter.PrintFormattedException(
          msg='Exception from DidRunUserStory: ')

class UserStoryGroup(object):
  def __init__(self, shared_user_story_state_class):
    self._shared_user_story_state_class = shared_user_story_state_class
    self._user_stories = []

  @property
  def shared_user_story_state_class(self):
    return self._shared_user_story_state_class

  @property
  def user_stories(self):
    return self._user_stories

  def AddUserStory(self, user_story):
    assert (user_story.shared_user_story_state_class is
            self._shared_user_story_state_class)
    self._user_stories.append(user_story)


def StoriesGroupedByStateClass(user_story_set, allow_multiple_groups):
  """ Returns a list of user story groups which each contains user stories with
  the same shared_user_story_state_class.

  Example:
    Assume A1, A2, A3 are user stories with same shared user story class, and
    similar for B1, B2.
    If their orders in user story set is A1 A2 B1 B2 A3, then the grouping will
    be [A1 A2] [B1 B2] [A3].

  It's purposefully done this way to make sure that order of user
  stories are the same of that defined in user_story_set. It's recommended that
  user stories with the same states should be arranged next to each others in
  user story sets to reduce the overhead of setting up & tearing down the
  shared user story state.
  """
  user_story_groups = []
  user_story_groups.append(
      UserStoryGroup(user_story_set[0].shared_user_story_state_class))
  for user_story in user_story_set:
    if (user_story.shared_user_story_state_class is not
        user_story_groups[-1].shared_user_story_state_class):
      if not allow_multiple_groups:
        raise ValueError('This UserStorySet is only allowed to have one '
                         'SharedUserStoryState but contains the following '
                         'SharedUserStoryState classes: %s, %s.\n Either '
                         'remove the extra SharedUserStoryStates or override '
                         'allow_mixed_story_states.' % (
                         user_story_groups[-1].shared_user_story_state_class,
                         user_story.shared_user_story_state_class))
      user_story_groups.append(
          UserStoryGroup(user_story.shared_user_story_state_class))
    user_story_groups[-1].AddUserStory(user_story)
  return user_story_groups


def Run(test, user_story_set, expectations, finder_options, results,
        max_failures=None):
  """Runs a given test against a given page_set with the given options.

  Stop execution for unexpected exceptions such as KeyboardInterrupt.
  We "white list" certain exceptions for which the user story runner
  can continue running the remaining user stories.
  """
  # Filter page set based on options.
  user_stories = filter(user_story_filter.UserStoryFilter.IsSelected,
                        user_story_set)

  if (not finder_options.use_live_sites and user_story_set.bucket and
      finder_options.browser_options.wpr_mode != wpr_modes.WPR_RECORD):
    serving_dirs = user_story_set.serving_dirs
    for directory in serving_dirs:
      cloud_storage.GetFilesInDirectoryIfChanged(directory,
                                                 user_story_set.bucket)
    if not _UpdateAndCheckArchives(
        user_story_set.archive_data_file, user_story_set.wpr_archive_info,
        user_stories):
      return

  if not user_stories:
    return

  # Effective max failures gives priority to command-line flag value.
  effective_max_failures = finder_options.max_failures
  if effective_max_failures is None:
    effective_max_failures = max_failures

  user_story_groups = StoriesGroupedByStateClass(
      user_stories,
      user_story_set.allow_mixed_story_states)

  for group in user_story_groups:
    state = None
    try:
      for _ in xrange(finder_options.pageset_repeat):
        for user_story in group.user_stories:
          for _ in xrange(finder_options.page_repeat):
            if not state:
              state = group.shared_user_story_state_class(
                  test, finder_options, user_story_set)
            results.WillRunPage(user_story)
            try:
              _WaitForThermalThrottlingIfNeeded(state.platform)
              _RunUserStoryAndProcessErrorIfNeeded(
                  expectations, user_story, results, state)
            except exceptions.Error:
              # Catch all Telemetry errors to give the story a chance to retry.
              # The retry is enabled by tearing down the state and creating
              # a new state instance in the next iteration.
              try:
                # If TearDownState raises, do not catch the exception.
                # (The Error was saved as a failure value.)
                state.TearDownState(results)
              finally:
                # Later finally-blocks use state, so ensure it is cleared.
                state = None
            finally:
              has_existing_exception = sys.exc_info() is not None
              try:
                if state:
                  _CheckThermalThrottling(state.platform)
                results.DidRunPage(user_story)
              except Exception:
                if not has_existing_exception:
                  raise
                # Print current exception and propagate existing exception.
                exception_formatter.PrintFormattedException(
                    msg='Exception from result processing:')
          if (effective_max_failures is not None and
              len(results.failures) > effective_max_failures):
            logging.error('Too many failures. Aborting.')
            return
    finally:
      if state:
        has_existing_exception = sys.exc_info() is not None
        try:
          state.TearDownState(results)
        except Exception:
          if not has_existing_exception:
            raise
          # Print current exception and propagate existing exception.
          exception_formatter.PrintFormattedException(
              msg='Exception from TearDownState:')


def _UpdateAndCheckArchives(archive_data_file, wpr_archive_info,
                            filtered_user_stories):
  """Verifies that all user stories are local or have WPR archives.

  Logs warnings and returns False if any are missing.
  """
  # Report any problems with the entire user story set.
  if any(not user_story.is_local for user_story in filtered_user_stories):
    if not archive_data_file:
      logging.error('The user story set is missing an "archive_data_file" '
                    'property.\nTo run from live sites pass the flag '
                    '--use-live-sites.\nTo create an archive file add an '
                    'archive_data_file property to the user story set and then '
                    'run record_wpr.')
      raise ArchiveError('No archive data file.')
    if not wpr_archive_info:
      logging.error('The archive info file is missing.\n'
                    'To fix this, either add svn-internal to your '
                    '.gclient using http://goto/read-src-internal, '
                    'or create a new archive using record_wpr.')
      raise ArchiveError('No archive info file.')
    wpr_archive_info.DownloadArchivesIfNeeded()

  # Report any problems with individual user story.
  user_stories_missing_archive_path = []
  user_stories_missing_archive_data = []
  for user_story in filtered_user_stories:
    if not user_story.is_local:
      archive_path = wpr_archive_info.WprFilePathForUserStory(user_story)
      if not archive_path:
        user_stories_missing_archive_path.append(user_story)
      elif not os.path.isfile(archive_path):
        user_stories_missing_archive_data.append(user_story)
  if user_stories_missing_archive_path:
    logging.error(
        'The user story set archives for some user stories do not exist.\n'
        'To fix this, record those user stories using record_wpr.\n'
        'To ignore this warning and run against live sites, '
        'pass the flag --use-live-sites.')
    logging.error(
        'User stories without archives: %s',
        ', '.join(user_story.display_name
                  for user_story in user_stories_missing_archive_path))
  if user_stories_missing_archive_data:
    logging.error(
        'The user story set archives for some user stories are missing.\n'
        'Someone forgot to check them in, uploaded them to the '
        'wrong cloud storage bucket, or they were deleted.\n'
        'To fix this, record those user stories using record_wpr.\n'
        'To ignore this warning and run against live sites, '
        'pass the flag --use-live-sites.')
    logging.error(
        'User stories missing archives: %s',
        ', '.join(user_story.display_name
                  for user_story in user_stories_missing_archive_data))
  if user_stories_missing_archive_path or user_stories_missing_archive_data:
    raise ArchiveError('Archive file is missing user stories.')
  # Only run valid user stories if no problems with the user story set or
  # individual user stories.
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
