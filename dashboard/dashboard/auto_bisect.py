# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to automatically run bisects."""

import datetime

from dashboard import bisect_group
from dashboard import datastore_hooks
from dashboard import request_handler
from dashboard import start_try_job
from dashboard.models import anomaly
from dashboard.models import try_job

# Days between successive bisect restarts.
_BISECT_RESTART_PERIOD_DAYS = [0, 1, 7, 14]


class AutoBisectHandler(request_handler.RequestHandler):
  """URL endpoint for a cron job to automatically run bisects."""

  def get(self):
    """A get request is the same a post request for this endpoint."""
    self.post()

  def post(self):
    """Runs auto bisects."""
    if 'stats' in self.request.query_string:
      self.RenderHtml('result.html', _PrintStartedAndFailedBisectJobs())
      return
    datastore_hooks.SetPrivilegedRequest()
    _RestartBisects()


def _RestartBisects():
  """Restarts failed bisect jobs.

  For bisect job that failed for the first time, restart it immediately.
  For following retries, use bisect_group to craft different bisect config
  and restart the bisect. Bisect jobs that ran out of retries will be deleted.
  """
  bisect_jobs = try_job.TryJob.query(try_job.TryJob.status == 'failed').fetch()
  for job in bisect_jobs:
    if job.run_count > 0:
      if job.run_count <= len(_BISECT_RESTART_PERIOD_DAYS):
        if _IsBisectJobDueForRestart(job):
          if job.run_count == 1:
            start_try_job.PerformBisect(job)
          elif job.bug_id:
            StartBisect(job)
      else:
        if job.bug_id:
          comment = ('Failed to run bisect %s times.'
                     'Stopping automatic restart for this job.' %
                     job.run_count)
          start_try_job.LogBisectResult(job.bug_id, comment)
        job.key.delete()


def StartBisect(bisect_job):
  """Chooses a bisect config depending on job's run count and run bisect.

  In this function we're setting the "config" property of the TryJob entity
  that gets passed in, so it's OK to pass in a TryJob entity whose "config"
  property is None.

  Args:
    bisect_job: TryJob entity with initialized bot name and config.

  Returns:
    A dictionary containing the result; if successful, this dictionary contains
    the field "issue_id", otherwise it contains "error".
  """
  if bisect_job.use_buildbucket:
    return {'error': 'Buildbucket not yet supported for 3 or more retries.'}
  anomalies = anomaly.Anomaly.query(
      anomaly.Anomaly.bug_id == bisect_job.bug_id).fetch()
  if not anomalies:
    return {'error': 'No alerts found for this bug.'}

  good_revision, bad_revision = bisect_group.ChooseRevisionRange(anomalies)
  if not good_revision or not bad_revision:
    return {'error': 'No good or bad revision found.'}

  # TODO(qyearsley): Add test coverage. See http://crbug.com/447432
  test = bisect_group.ChooseTest(anomalies, bisect_job.run_count)
  if not test:
    return {'error': 'Cannot figure out a test.'}

  metric = start_try_job.GuessMetric(test.test_path)

  bisect_bot = start_try_job.GuessBisectBot(test.bot_name)
  if not bisect_bot or '_' not in bisect_bot:
    return {'error': 'Cannot figure out a bisect bot.'}

  new_bisect_config = start_try_job.GetBisectConfig(
      bisect_bot, test.suite_name, metric, good_revision, bad_revision,
      10, 20, 25, bisect_job.bug_id, use_archive='true')

  if new_bisect_config.get('error'):
    return new_bisect_config

  bisect_job.config = new_bisect_config['config']
  bisect_job.bot = bisect_bot
  result = start_try_job.PerformBisect(bisect_job)
  return result


def _IsBisectJobDueForRestart(bisect_job):
  """Whether bisect job is due for restart."""
  old_timestamp = (datetime.datetime.now() - datetime.timedelta(
      days=_BISECT_RESTART_PERIOD_DAYS[bisect_job.run_count - 1]))
  if bisect_job.last_ran_timestamp < old_timestamp:
    return True
  return False


def _PrintStartedAndFailedBisectJobs():
  """Print started and failed bisect jobs in datastore."""
  failed_jobs = try_job.TryJob.query(
      try_job.TryJob.status == 'failed').fetch()
  started_jobs = try_job.TryJob.query(
      try_job.TryJob.status == 'started').fetch()
  failed_jobs.sort(key=lambda b: b.run_count)
  started_jobs.sort(key=lambda b: b.run_count)

  return {
      'headline': 'Bisect Jobs',
      'results': [
          _JobsListResult('Failed jobs', failed_jobs),
          _JobsListResult('Started jobs', started_jobs),
      ]
  }


def _JobsListResult(title, jobs):
  """Returns one item in a list of results to be displayed on result.html."""
  return {
      'name': '%s: %d' % (title, len(jobs)),
      'value': '\n'.join(_JobLine(job) for job in jobs),
      'class': 'results-pre'
  }


def _JobLine(job):
  """Returns a string with information about one TryJob entity."""
  config = job.config.replace('\n', '') if job.config else 'No config.'
  return 'Run count %d. Bug ID %d. %s' % (job.run_count, job.bug_id, config)
