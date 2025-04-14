# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""URL endpoint containing server-side functionality for pinpoint jobs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging
import six

from google.appengine.ext import ndb

from dashboard.common import descriptor
from dashboard.common import isolate_targets as iso
from dashboard.common import math_utils
from dashboard.common import utils
from dashboard.common import defaults
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.services import crrev_service
from dashboard.services import pinpoint_service

from flask import request

_NON_CHROME_TARGETS = ['v8']
_SUITE_CRREV_CONFIGS = {
    'v8': ['chromium', 'v8/v8'],
    'webrtc_perf_tests': ['webrtc', 'src'],
}


class InvalidParamsError(Exception):
  pass


def PinpointNewBisectPost():
  return json.dumps(NewPinpointBisect(request.values))


def PinpointNewPrefillPost():
  t = utils.TestKey(request.values.get('test_path')).get()
  return json.dumps({'story_filter': t.unescaped_story_name})


def PinpointNewPerfTryPost():
  try:
    pinpoint_params = PinpointParamsFromPerfTryParams(request.values)
  except InvalidParamsError as e:
    return json.dumps({'error': str(e)})

  return json.dumps(pinpoint_service.NewJob(pinpoint_params))


def NewPinpointBisect(job_params):
  logging.info('Job Params: %s', job_params)

  try:
    pinpoint_params = PinpointParamsFromBisectParams(job_params)
    logging.info('[Pinpoint Request] Pinpoint Params: %s', pinpoint_params)
  except InvalidParamsError as e:
    logging.error("[Pinpoint Request] Invalid params! %s", str(e))
    return {'error': str(e)}

  logging.debug(
      '[Pinpoint Request] Making the request to legacy Pinpoint for bisection')
  results = pinpoint_service.NewJob(pinpoint_params)
  logging.info('[Pinpoint Request] Pinpoint Service Response: %s', results)

  # We might get a list of Anomaly IDs instead of a list of urlsafe keys.
  # In that case, they need to be translated.
  alert_keys = []
  if 'alert_ids' in job_params:
    alert_ids = json.loads(job_params.get('alert_ids'))
    if alert_ids:
      logging.info(
          '[Pinpoint Request] Translating alert IDs to urlsafe keys: %s',
          alert_ids)
      alert_keys = [ndb.Key('Anomaly', id).urlsafe() for id in alert_ids]
  elif 'alerts' in job_params:
    alert_keys = json.loads(job_params.get('alerts'))

  if 'jobId' in results and alert_keys:
    for alert_urlsafe_key in alert_keys:
      alert = ndb.Key(urlsafe=alert_urlsafe_key).get()
      alert.pinpoint_bisects.append(results['jobId'])
      alert.put()

  return results


def _GitHashToCommitPosition(commit_position):
  try:
    commit_position = int(commit_position)
  except ValueError as e:
    result = crrev_service.GetCommit(commit_position)
    if 'error' in result:
      six.raise_from(
          InvalidParamsError('Error retrieving commit info: %s' %
                             result['error'].get('message')), e)
    commit_position = int(result['number'])
  return commit_position


def FindMagnitudeBetweenCommits(test_key, start_commit, end_commit):
  start_commit = _GitHashToCommitPosition(start_commit)
  end_commit = _GitHashToCommitPosition(end_commit)

  test = test_key.get()
  num_points = anomaly_config.GetAnomalyConfigDict(test).get(
      'min_segment_size', defaults.MIN_SEGMENT_SIZE)
  start_rows = graph_data.GetRowsForTestBeforeAfterRev(test_key, start_commit,
                                                       num_points, 0)
  end_rows = graph_data.GetRowsForTestBeforeAfterRev(test_key, end_commit, 0,
                                                     num_points)

  if not start_rows or not end_rows:
    return None

  median_before = math_utils.Median([r.value for r in start_rows])
  median_after = math_utils.Median([r.value for r in end_rows])

  return median_after - median_before


def ResolveToGitHash(commit_position, suite=None, crrev=None):
  crrev = crrev or crrev_service
  try:
    int(commit_position)
    if suite in _SUITE_CRREV_CONFIGS:
      project, repo = _SUITE_CRREV_CONFIGS[suite]
    else:
      project, repo = 'chromium', 'chromium/src'
    result = crrev.GetNumbering(
        number=commit_position,
        numbering_identifier='refs/heads/main',
        numbering_type='COMMIT_POSITION',
        project=project,
        repo=repo)
    if 'error' in result:
      raise InvalidParamsError('Error retrieving commit info: %s' %
                               result['error'].get('message'))
    return result['git_sha']
  except ValueError:
    pass

  # It was probably a git hash, so just return as is
  return commit_position


def GetIsolateTarget(bot_name, suite):
  if suite in _NON_CHROME_TARGETS:
    return ''

  # ChromeVR
  if suite.startswith('xr.'):
    return 'vr_perf_tests'

  # WebRTC perf tests
  if suite == 'webrtc_perf_tests':
    return 'webrtc_perf_tests'

  # This is a special-case for webview, which we probably don't need to handle
  # in the Dashboard (instead should just support in Pinpoint through
  # configuration).
  if 'webview' in bot_name.lower():
    return 'performance_webview_test_suite'

  # Special cases for CrOS tests -
  # performance_test_suites are device type specific.
  if 'eve' in bot_name.lower():
    return 'performance_test_suite_eve'
  if bot_name == 'lacros-x86-perf':
    return 'performance_test_suite_octopus'

  # WebEngine tests are specific to Fuchsia devices only.
  if 'fuchsia-perf' in bot_name.lower():
    return 'performance_web_engine_test_suite'

  return iso.GetAndroidTarget(
      bot_name,
      InvalidParamsError(
          'Given Android bot %s does not have an isolate mapped to it' %
          bot_name))

def ParseGroupingLabelChartNameAndTraceName(test_path):
  """Returns grouping_label, chart_name, trace_name from a test path."""
  test_path_parts = test_path.split('/')
  suite = test_path_parts[2]
  if suite in _NON_CHROME_TARGETS:
    return '', '', ''

  test = ndb.Key('TestMetadata', '/'.join(test_path_parts)).get()
  grouping_label, chart_name, trace_name = utils.ParseTelemetryMetricParts(
      test_path)
  if trace_name and test.unescaped_story_name:
    trace_name = test.unescaped_story_name
  return grouping_label, chart_name, trace_name


def ParseStatisticNameFromChart(chart_name):
  chart_name_parts = chart_name.split('_')
  statistic_name = ''

  if chart_name_parts[-1] in descriptor.STATISTICS:
    chart_name = '_'.join(chart_name_parts[:-1])
    statistic_name = chart_name_parts[-1]
  return chart_name, statistic_name


def PinpointParamsFromPerfTryParams(params):
  """Takes parameters from Dashboard's pinpoint-perf-job-dialog and returns
  a dict with parameters for a new Pinpoint job.

  Args:
    params: A dict in the following format:
    {
        'test_path': Test path for the metric being bisected.
        'start_commit': Git hash or commit position of earlier revision.
        'end_commit': Git hash or commit position of later revision.
        'extra_test_args': Extra args for the swarming job.
    }

  Returns:
    A dict of params for passing to Pinpoint to start a job, or a dict with an
    'error' field.
  """
  if not utils.IsValidSheriffUser(params.get('user', '')):
    user = utils.GetEmail()
    raise InvalidParamsError('User "%s" not authorized.' % user)

  test_path = params.get('test_path')
  if not test_path:
    raise InvalidParamsError('Test path is required.')

  test_path_parts = test_path.split('/')
  bot_name = test_path_parts[1]
  suite = test_path_parts[2]

  start_commit = params.get('start_commit')
  if not start_commit:
    raise InvalidParamsError('Start commit is required.')

  end_commit = params.get('end_commit')
  if not end_commit:
    raise InvalidParamsError('End commit is required.')

  start_git_hash = ResolveToGitHash(start_commit, suite)
  end_git_hash = ResolveToGitHash(end_commit, suite)
  story_filter = params.get('story_filter')
  if not story_filter:
    raise InvalidParamsError('Story is required.')

  # Pinpoint also requires you specify which isolate target to run the
  # test, so we derive that from the suite name. Eventually, this would
  # ideally be stored in a SparseDiagnostic but for now we can guess.
  target = GetIsolateTarget(bot_name, suite)

  extra_test_args = params.get('extra_test_args')

  email = utils.GetEmail()
  job_name = 'Try job on %s/%s' % (bot_name, suite)

  pinpoint_params = {
      'comparison_mode': 'try',
      'configuration': bot_name,
      'benchmark': suite,
      'base_git_hash': start_git_hash,
      'end_git_hash': end_git_hash,
      'extra_test_args': extra_test_args,
      'target': target,
      'user': email,
      'name': job_name
  }

  if story_filter:
    pinpoint_params['story'] = story_filter

  logging.debug('[Pinpoint Request] Pinpoint Params: %s', pinpoint_params)

  return pinpoint_params

def _GetUrlSafeKey(params):
  """Returns the urlsafe key for the anomaly from the request parameters."""
  if params.get('alert_ids'):
    alert_ids = json.loads(params.get('alert_ids'))
    if alert_ids:
      return ndb.Key('Anomaly', alert_ids[0]).urlsafe()
  elif params.get('alerts'):
    alert_keys = json.loads(params.get('alerts'))
    if alert_keys:
      return alert_keys[0]
  return ''


def PinpointParamsFromBisectParams(params):
  """Takes parameters from Dashboard's pinpoint-job-dialog and returns
  a dict with parameters for a new Pinpoint job.

  Args:
    params: A dict in the following format:
    {
        'test_path': Test path for the metric being bisected.
        'start_git_hash': Git hash of earlier revision.
        'end_git_hash': Git hash of later revision.
        'bug_id': Associated bug.
        'project_id': Associated Monorail project.
        'story_filter': The story to run in the bisect request.
    }

  Returns:
    A dict of params for passing to Pinpoint to start a job, or a dict with an
    'error' field.
  """
  user_email = params.get('user') or utils.GetEmail()
  if not utils.IsValidSheriffUser(user_email):
    logging.error('[Pinpoint Request] User "%s" not authorized.', user_email)
    raise InvalidParamsError('User "%s" not authorized.' % user_email)

  # story_filter renamed to story in Skia
  story_filter = params.get('story_filter', params.get('story'))
  if not story_filter:
    logging.error('[Pinpoint Request] Story is required.')
    raise InvalidParamsError('Story is required.')

  test_path = params.get('test_path')
  if not test_path:
    logging.error('[Pinpoint Request] Test path is required.')
    raise InvalidParamsError('Test path is required.')

  configuration = params.get('configuration')  # bot_name
  benchmark = params.get('benchmark')  # suite

  if not configuration and not benchmark:
    test_path_parts = test_path.split('/')
    if len(test_path_parts) < 2:
      logging.error(
          '[Pinpoint Request] Expecting test path be slash delimited, '
          'received %s', test_path)
      raise InvalidParamsError('Invalid test path provided.')
    configuration = test_path_parts[1]
    benchmark = test_path_parts[2]

  # If functional bisects are speciied, Pinpoint expects these parameters to be
  # empty.
  # bisect_mode renamed to comparison_mode for Skia. For bisect, Skia does not
  # support functional bisect.
  bisect_mode = params.get('bisect_mode', params.get('comparison_mode'))
  if bisect_mode not in ('performance', 'functional'):
    logging.error('[Pinpoint Request] Invalid bisect mode %s specified.',
                  bisect_mode)
    raise InvalidParamsError('Invalid bisect mode %s specified.' % bisect_mode)

  # start_commit and end_commit both renamed to start_git_hash and end_git_hash
  # from Skia, though, they are utilized as commit positions.
  start_commit = params.get('start_commit', params.get('start_git_hash'))
  if not start_commit:
    logging.error('[Pinpoint Request] Start commit is required.')
    raise InvalidParamsError('Start commit is required.')

  end_commit = params.get('end_commit', params.get('end_git_hash'))
  if not end_commit:
    logging.error('[Pinpoint Request] Start commit is required.')
    raise InvalidParamsError('End commit is required.')

  start_git_hash = ResolveToGitHash(start_commit, benchmark)
  logging.debug('[Pinpoint Request] Start git hash: %s', start_git_hash)
  end_git_hash = ResolveToGitHash(end_commit, benchmark)
  logging.debug('[Pinpoint Request] End git hash: %s', end_git_hash)


  # Pinpoint also requires you specify which isolate target to run the
  # test, so we derive that from the suite name. Eventually, this would
  # ideally be stored in a SparesDiagnostic but for now we can guess.
  target = GetIsolateTarget(configuration, benchmark)
  logging.debug('[Pinpoint Request] Target %s from bot name %s and suite %s',
                target, configuration, benchmark)

  job_name = '%s bisect on %s/%s' % (bisect_mode.capitalize(), configuration,
                                     benchmark)

  alert_key = _GetUrlSafeKey(params)

  alert_magnitude = None
  if alert_key:
    alert = ndb.Key(urlsafe=alert_key).get()
    alert_magnitude = alert.median_after_anomaly - alert.median_before_anomaly

  if not alert_magnitude:
    alert_magnitude = FindMagnitudeBetweenCommits(
        utils.TestKey(test_path), start_commit, end_commit)
  elif params.get('comparison_magnitude'):
    alert_magnitude = params.get('comparison_magnitude')

  if isinstance(params['bug_id'], int):
    issue_id = params['bug_id'] if params['bug_id'] > 0 else None
  else:
    issue_id = int(params['bug_id']) if params['bug_id'].isdigit() else None
  issue = anomaly.Issue(
      project_id=params.get('project_id', 'chromium'), issue_id=issue_id)

  return pinpoint_service.MakeBisectionRequest(
      test=utils.TestKey(test_path).get(),
      commit_range=pinpoint_service.CommitRange(
          start=start_git_hash, end=end_git_hash),
      issue=issue,
      comparison_mode=bisect_mode,
      target=target,
      comparison_magnitude=alert_magnitude,
      user=user_email,
      name=job_name,
      story_filter=story_filter,
      pin=params.get('pin'),
      tags={
          'test_path': test_path,
          'alert': six.ensure_str(alert_key),
      },
  )
