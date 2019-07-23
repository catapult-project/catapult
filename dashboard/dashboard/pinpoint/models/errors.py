# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import


class FatalError(Exception):
  def __init__(self, message):
    super(FatalError, self).__init__(message)


class InformationalError(Exception):
  def __init__(self, message):
    super(InformationalError, self).__init__(message)


class RecoverableError(Exception):
  pass


class BuildIsolateNotFound(FatalError):
  def __init__(self):
    super(BuildIsolateNotFound, self).__init__(
        "The build was reported to have completed successfully, but Pinpoint "\
        "is unable to find the isolate that was produced and will be unable "\
        "to run any tests against this revision.")


class BuildFailed(InformationalError):
  def __init__(self, reason):
    super(BuildFailed, self).__init__(
        'Encountered an %s error while attempting to build this revision. '\
        'Pinpoint will be unable to run any tests against this '\
        'revision.' % reason)


class BuildCancelled(InformationalError):
  def __init__(self, reason):
    super(BuildCancelled, self).__init__(
        'The build was cancelled with reason: %s. "\
        "Pinpoint will be unable to run any tests against this "\
        "revision.'                    % reason)


class BuildGerritUrlNotFound(InformationalError):
  def __init__(self, reason):
    super(BuildGerritUrlNotFound, self).__init__(
        'Unable to find gerrit url for commit %s. Pinpoint will be unable '\
        'to run any tests against this revision.' % reason)


class BuildGerritURLInvalid(InformationalError):
  def __init__(self, reason):
    super(BuildGerritURLInvalid, self).__init__(
        'Invalid url: %s. Pinpoint currently only supports the fully '\
        'redirected patch URL, ie. https://chromium-review.googlesource.com/'\
        'c/chromium/src/+/12345' % reason)


class CancelError(InformationalError):

  def __init__(self, reason):
    super(CancelError,
          self).__init__('Cancellation request failed: {}'.format(reason))


class SwarmingExpired(FatalError):
  def __init__(self):
    super(SwarmingExpired, self).__init__(
        'The test was successfully queued in swarming, but expired. This is '\
        'likely due to the bots being overloaded, dead, or misconfigured. '\
        'Pinpoint will stop this job to avoid potentially overloading the '\
        'bots further.')


class SwarmingTaskError(InformationalError):
  def __init__(self, reason):
    super(SwarmingTaskError, self).__init__(
        'The swarming task failed with state "%s". This generally indicates '\
        'that the test was successfully started, but was stopped prematurely. '\
        'This error could be something like the bot died, the test timed out, '\
        'or the task was manually canceled.' % reason)


class SwarmingTaskFailed(InformationalError):
  """Raised when the test fails."""
  def __init__(self, taskOutput):
    super(SwarmingTaskFailed, self).__init__(
        'The test ran but failed. This is likely to a problem with the test '\
        'itself either being broken or flaky in the range specified.\n\n'\
        'The test failed with the following error:')
    self.task_output = taskOutput


class SwarmingTaskFailedNoException(InformationalError):
  def __init__(self):
    super(SwarmingTaskFailedNoException, self).__init__(
        'The test was run but failed and Pinpoint was unable to parse the '\
        'exception from the logs.')


class SwarmingNoBots(InformationalError):
  def __init__(self):
    super(SwarmingNoBots, self).__init__(
        "There doesn't appear to be any bots available to run the "\
        "performance test. Either all the swarming devices are offline, or "\
        "they're misconfigured.")


class ReadValueNoValues(InformationalError):
  def __init__(self):
    super(ReadValueNoValues, self).__init__(
        'The test ran successfully, but the output failed to contain any '\
        'valid values. This is likely due to a problem with the test itself '\
        'in this range.')


class ReadValueNotFound(InformationalError):
  def __init__(self, reason):
    super(ReadValueNotFound, self).__init__(
        "The test ran successfully, but the metric specified (%s) wasn't "\
        "found in the output. Either the metric specified was invalid, or "\
        "there's a problem with the test itself in this range." % reason)


class ReadValueUnknownStat(InformationalError):
  def __init__(self, reason):
    super(ReadValueUnknownStat, self).__init__(
        "The test ran successfully, but the statistic specified (%s) wasn't "\
        "found in the output. Either the metric specified was invalid, "\
        "or there's a problem with the test itself in this range." % reason)


class ReadValueChartNotFound(InformationalError):
  def __init__(self, reason):
    super(ReadValueChartNotFound, self).__init__(
        "The test ran successfully, but the chart specified (%s) wasn't "\
        "found in the output. Either the chart specified was invalid, or "\
        "there's a problem with the test itself in this range." % reason)


class ReadValueTraceNotFound(InformationalError):
  def __init__(self, reason):
    super(ReadValueTraceNotFound, self).__init__(
        "The test ran successfully, but the trace specified (%s) wasn't "\
        "found in the output. Either the trace specified was invalid, or "\
        "there's a problem with the test itself in this range." % reason)


class ReadValueNoFile(InformationalError):
  def __init__(self, reason):
    super(ReadValueNoFile, self).__init__(
        'The test ran successfully but failed to produce an expected '\
        'output file: %s. This is likely due to a problem with the test '\
        'itself in this range.' % reason)


class AllRunsFailed(FatalError):
  def __init__(self, exc_count, att_count, exc):
    super(AllRunsFailed, self).__init__(
        'All of the runs failed. The most common error (%d/%d runs) '\
        'was:\n%s' % (exc_count, att_count, exc))


RETRY_LIMIT = "Pinpoint has hit its' retry limit and will terminate this job."

RETRY_FAILED = "Pinpoint wasn't able to reschedule itself to run again."

REFRESH_FAILURE = 'An unknown failure occurred during the run.\n'\
    'Please file a bug under Speed>Bisection with this job.'

TRANSIENT_ERROR_MSG = 'Pinpoint encountered an error while connecting to an '\
    'external service. The service is either down, unresponsive, or the '\
    'problem was transient. These are typically retried by Pinpoint, so '\
    'if you see this, please file a bug.'

FATAL_ERROR_MSG = 'Pinpoint encountered a fatal internal error and cannot '\
    'continue. Please file an issue with Speed>Bisection.'
