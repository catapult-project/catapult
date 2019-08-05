# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint containing server-side functionality for pinpoint jobs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import logging

from google.appengine.ext import ndb

from dashboard import find_change_points
from dashboard import start_try_job
from dashboard.common import descriptor
from dashboard.common import math_utils
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.services import crrev_service
from dashboard.services import pinpoint_service

_NON_CHROME_TARGETS = ['v8']
# TODO(simonhatch): Find a more official way to lookup isolate targets for
# suites; crbug.com/950165
_ISOLATE_TARGETS = [
    'angle_perftests', 'base_perftests', 'cc_perftests', 'gpu_perftests',
    'load_library_perf_tests', 'media_perftests', 'net_perftests',
    'performance_browser_tests', 'tracing_perftests']
_SUITE_CRREV_CONFIGS = {
    'v8': ['chromium', 'v8/v8'],
}


class InvalidParamsError(Exception):
  pass


class PinpointNewPrefillRequestHandler(request_handler.RequestHandler):
  def post(self):
    story_filter = start_try_job.GuessStoryFilter(self.request.get('test_path'))
    self.response.write(json.dumps({'story_filter': story_filter}))


class PinpointNewBisectRequestHandler(request_handler.RequestHandler):
  def post(self):
    job_params = dict(
        (a, self.request.get(a)) for a in self.request.arguments())
    self.response.write(json.dumps(NewPinpointBisect(job_params)))


def NewPinpointBisect(job_params):
  logging.info('Job Params: %s', job_params)

  try:
    pinpoint_params = PinpointParamsFromBisectParams(job_params)
    logging.info('Pinpoint Params: %s', pinpoint_params)
  except InvalidParamsError as e:
    return {'error': e.message}

  results = pinpoint_service.NewJob(pinpoint_params)
  logging.info('Pinpoint Service Response: %s', results)

  alert_keys = job_params.get('alerts')
  if 'jobId' in results and alert_keys:
    alerts = json.loads(alert_keys)
    for alert_urlsafe_key in alerts:
      alert = ndb.Key(urlsafe=alert_urlsafe_key).get()
      alert.pinpoint_bisects.append(results['jobId'])
      alert.put()

  return results


class PinpointNewPerfTryRequestHandler(request_handler.RequestHandler):
  def post(self):
    job_params = dict(
        (a, self.request.get(a)) for a in self.request.arguments())

    try:
      pinpoint_params = PinpointParamsFromPerfTryParams(job_params)
    except InvalidParamsError as e:
      self.response.write(json.dumps({'error': e.message}))
      return

    self.response.write(json.dumps(pinpoint_service.NewJob(pinpoint_params)))


def ParseMetricParts(test_path_parts):
  metric_parts = test_path_parts[3:]

  # Normal test path structure, ie. M/B/S/foo/bar.html
  if len(metric_parts) == 2:
    return '', metric_parts[0], metric_parts[1]

  # 3 part structure, so there's a TIR label in there.
  # ie. M/B/S/timeToFirstMeaningfulPaint_avg/load_tools/load_tools_weather
  if len(metric_parts) == 3:
    return metric_parts[1], metric_parts[0], metric_parts[2]

  # Should be something like M/B/S/EventsDispatching where the trace_name is
  # left empty and implied to be summary.
  assert len(metric_parts) == 1
  return '', metric_parts[0], ''


def _GitHashToCommitPosition(commit_position):
  try:
    commit_position = int(commit_position)
  except ValueError:
    result = crrev_service.GetCommit(commit_position)
    if 'error' in result:
      raise InvalidParamsError(
          'Error retrieving commit info: %s' % result['error'].get('message'))
    commit_position = int(result['number'])
  return commit_position


def FindMagnitudeBetweenCommits(test_key, start_commit, end_commit):
  start_commit = _GitHashToCommitPosition(start_commit)
  end_commit = _GitHashToCommitPosition(end_commit)

  test = test_key.get()
  num_points = anomaly_config.GetAnomalyConfigDict(test).get(
      'min_segment_size', find_change_points.MIN_SEGMENT_SIZE)
  start_rows = graph_data.GetRowsForTestBeforeAfterRev(
      test_key, start_commit, num_points, 0)
  end_rows = graph_data.GetRowsForTestBeforeAfterRev(
      test_key, end_commit, 0, num_points)

  if not start_rows or not end_rows:
    return None

  median_before = math_utils.Median([r.value for r in start_rows])
  median_after = math_utils.Median([r.value for r in end_rows])

  return median_after - median_before


def ResolveToGitHash(commit_position, suite):
  try:
    int(commit_position)
    if suite in _SUITE_CRREV_CONFIGS:
      project, repo = _SUITE_CRREV_CONFIGS[suite]
    else:
      project, repo = 'chromium', 'chromium/src'
    result = crrev_service.GetNumbering(
        number=commit_position,
        numbering_identifier='refs/heads/master',
        numbering_type='COMMIT_POSITION',
        project=project,
        repo=repo)
    if 'error' in result:
      raise InvalidParamsError(
          'Error retrieving commit info: %s' % result['error'].get('message'))
    return result['git_sha']
  except ValueError:
    pass

  # It was probably a git hash, so just return as is
  return commit_position


def _GetIsolateTarget(bot_name, suite, start_commit,
                      end_commit, only_telemetry=False):
  if suite in _NON_CHROME_TARGETS:
    return ''

  if suite in _ISOLATE_TARGETS:
    if only_telemetry:
      raise InvalidParamsError('Only telemetry is supported at the moment.')
    return suite

  # ChromeVR
  if suite.startswith('xr.'):
    return 'vr_perf_tests'

  try:
    # TODO: Remove this code path in 2019.
    average_commit = (int(start_commit) + int(end_commit)) / 2
    if 'android' in bot_name and average_commit < 572268:
      if 'webview' in bot_name.lower():
        return 'telemetry_perf_webview_tests'
      return 'telemetry_perf_tests'

    if 'win' in bot_name and average_commit < 571917:
      return 'telemetry_perf_tests'
  except ValueError:
    pass

  if 'webview' in bot_name.lower():
    return 'performance_webview_test_suite'
  return 'performance_test_suite'


def ParseTIRLabelChartNameAndTraceName(test_path_parts):
  """Returns tir_label, chart_name, trace_name from a test path."""
  suite = test_path_parts[2]
  if suite in _NON_CHROME_TARGETS:
    return '', '', ''

  test = ndb.Key('TestMetadata', '/'.join(test_path_parts)).get()
  tir_label, chart_name, trace_name = ParseMetricParts(test_path_parts)
  if trace_name and test.unescaped_story_name:
    trace_name = test.unescaped_story_name
  return tir_label, chart_name, trace_name


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
  if not utils.IsValidSheriffUser():
    user = utils.GetEmail()
    raise InvalidParamsError('User "%s" not authorized.' % user)

  test_path = params['test_path']
  test_path_parts = test_path.split('/')
  bot_name = test_path_parts[1]
  suite = test_path_parts[2]

  start_commit = params['start_commit']
  end_commit = params['end_commit']
  start_git_hash = ResolveToGitHash(start_commit, suite)
  end_git_hash = ResolveToGitHash(end_commit, suite)
  story_filter = params['story_filter']

  # Pinpoint also requires you specify which isolate target to run the
  # test, so we derive that from the suite name. Eventually, this would
  # ideally be stored in a SparesDiagnostic but for now we can guess.
  target = _GetIsolateTarget(bot_name, suite, start_commit,
                             end_commit, only_telemetry=True)

  extra_test_args = params['extra_test_args']

  email = utils.GetEmail()
  job_name = 'Try job on %s/%s' % (bot_name, suite)

  pinpoint_params = {
      'comparison_mode': 'try',
      'configuration': bot_name,
      'benchmark': suite,
      'start_git_hash': start_git_hash,
      'end_git_hash': end_git_hash,
      'extra_test_args': extra_test_args,
      'target': target,
      'user': email,
      'name': job_name
  }

  if story_filter:
    pinpoint_params['story'] = story_filter

  return pinpoint_params


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
    }

  Returns:
    A dict of params for passing to Pinpoint to start a job, or a dict with an
    'error' field.
  """
  if not utils.IsValidSheriffUser():
    user = utils.GetEmail()
    raise InvalidParamsError('User "%s" not authorized.' % user)

  test_path = params['test_path']
  test_path_parts = test_path.split('/')
  bot_name = test_path_parts[1]
  suite = test_path_parts[2]
  story_filter = params['story_filter']
  pin = params.get('pin')

  # If functional bisects are speciied, Pinpoint expects these parameters to be
  # empty.
  bisect_mode = params['bisect_mode']
  if bisect_mode != 'performance' and bisect_mode != 'functional':
    raise InvalidParamsError('Invalid bisect mode %s specified.' % bisect_mode)

  tir_label = ''
  chart_name = ''
  trace_name = ''
  if bisect_mode == 'performance':
    tir_label, chart_name, trace_name = ParseTIRLabelChartNameAndTraceName(
        test_path_parts)

  start_commit = params['start_commit']
  end_commit = params['end_commit']
  start_git_hash = ResolveToGitHash(start_commit, suite)
  end_git_hash = ResolveToGitHash(end_commit, suite)

  # Pinpoint also requires you specify which isolate target to run the
  # test, so we derive that from the suite name. Eventually, this would
  # ideally be stored in a SparesDiagnostic but for now we can guess.
  target = _GetIsolateTarget(bot_name, suite, start_commit, end_commit)

  email = utils.GetEmail()
  job_name = '%s bisect on %s/%s' % (bisect_mode.capitalize(), bot_name, suite)

  # Histogram names don't include the statistic, so split these
  chart_name, statistic_name = ParseStatisticNameFromChart(chart_name)

  alert_key = ''
  if params.get('alerts'):
    alert_keys = json.loads(params.get('alerts'))
    if alert_keys:
      alert_key = alert_keys[0]

  alert_magnitude = None
  if alert_key:
    alert = ndb.Key(urlsafe=alert_key).get()
    alert_magnitude = alert.median_after_anomaly - alert.median_before_anomaly

  if not alert_magnitude:
    alert_magnitude = FindMagnitudeBetweenCommits(
        utils.TestKey(test_path), start_commit, end_commit)

  pinpoint_params = {
      'configuration': bot_name,
      'benchmark': suite,
      'chart': chart_name,
      'start_git_hash': start_git_hash,
      'end_git_hash': end_git_hash,
      'bug_id': params['bug_id'],
      'comparison_mode': bisect_mode,
      'target': target,
      'user': email,
      'name': job_name,
      'tags': json.dumps({
          'test_path': test_path,
          'alert': alert_key
      }),
  }

  if alert_magnitude:
    pinpoint_params['comparison_magnitude'] = alert_magnitude
  if pin:
    pinpoint_params['pin'] = pin
  if statistic_name:
    pinpoint_params['statistic'] = statistic_name
  if story_filter:
    pinpoint_params['story'] = story_filter
  if tir_label:
    pinpoint_params['tir_label'] = tir_label
  if trace_name:
    pinpoint_params['trace'] = trace_name

  return pinpoint_params
