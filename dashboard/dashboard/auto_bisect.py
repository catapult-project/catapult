# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to automatically run bisects."""

import datetime
import logging

from dashboard import can_bisect
from dashboard import datastore_hooks
from dashboard import request_handler
from dashboard import start_try_job
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
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
    if _RestartFailedBisectJobs():
      utils.TickMonitoringCustomMetric('RestartFailedBisectJobs')


class NotBisectableError(Exception):
  """An error indicating that a bisect couldn't be automatically started."""
  pass


def _RestartFailedBisectJobs():
  """Restarts failed bisect jobs.

  Bisect jobs that ran out of retries will be deleted.

  Returns:
    True if all bisect jobs that were retried were successfully triggered,
    and False otherwise.
  """
  bisect_jobs = try_job.TryJob.query(try_job.TryJob.status == 'failed').fetch()
  all_successful = True
  for job in bisect_jobs:
    if job.run_count > 0:
      if job.run_count <= len(_BISECT_RESTART_PERIOD_DAYS):
        if _IsBisectJobDueForRestart(job):
          # Start bisect right away if this is the first retry. Otherwise,
          # try bisect with different config.
          if job.run_count == 1:
            try:
              start_try_job.PerformBisect(job)
            except request_handler.InvalidInputError as e:
              logging.error(e.message)
              all_successful = False
          elif job.bug_id:
            restart_successful = _RestartBisect(job)
            if not restart_successful:
              all_successful = False
      else:
        if job.bug_id:
          comment = ('Failed to run bisect %s times.'
                     'Stopping automatic restart for this job.' %
                     job.run_count)
          start_try_job.LogBisectResult(job.bug_id, comment)
        job.key.delete()
  return all_successful


def _RestartBisect(bisect_job):
  """Re-starts a bisect-job after modifying it's config based on run count.

  Args:
    bisect_job: TryJob entity with initialized bot name and config.

  Returns:
    True if the bisect was successfully triggered and False otherwise.
  """
  try:
    new_bisect_job = _MakeBisectTryJob(
        bisect_job.bug_id, bisect_job.run_count)
  except NotBisectableError:
    return False
  bisect_job.config = new_bisect_job.config
  bisect_job.bot = new_bisect_job.bot
  bisect_job.use_buildbucket = new_bisect_job.use_buildbucket
  bisect_job.put()
  try:
    start_try_job.PerformBisect(bisect_job)
  except request_handler.InvalidInputError as e:
    logging.error(e.message)
    return False
  return True


def StartNewBisectForBug(bug_id):
  """Tries to trigger a bisect job for the alerts associated with a bug.

  Args:
    bug_id: A bug ID number.

  Returns:
    If successful, a dict containing "issue_id" and "issue_url" for the
    bisect job. Otherwise, a dict containing "error", with some description
    of the reason why a job wasn't started.
  """
  try:
    bisect_job = _MakeBisectTryJob(bug_id)
  except NotBisectableError as e:
    return {'error': e.message}
  bisect_job_key = bisect_job.put()

  try:
    bisect_result = start_try_job.PerformBisect(bisect_job)
  except request_handler.InvalidInputError as e:
    bisect_result = {'error': e.message}
  if 'error' in bisect_result:
    bisect_job_key.delete()
  return bisect_result


def _MakeBisectTryJob(bug_id, run_count=0):
  """Tries to automatically select parameters for a bisect job.

  Args:
    bug_id: A bug ID which some alerts are associated with.
    run_count: An integer; this is supposed to represent the number of times
        that a bisect has been tried for this bug; it is used to try different
        config parameters on different re-try attempts.

  Returns:
    A TryJob entity, which has not yet been put in the datastore.

  Raises:
    NotBisectableError: A valid bisect config could not be created.
  """
  anomalies = anomaly.Anomaly.query(anomaly.Anomaly.bug_id == bug_id).fetch()
  if not anomalies:
    raise NotBisectableError('No Anomaly alerts found for this bug.')

  good_revision, bad_revision = _ChooseRevisionRange(anomalies)
  if not can_bisect.IsValidRevisionForBisect(good_revision):
    raise NotBisectableError('Invalid "good" revision: %s.' % good_revision)
  if not can_bisect.IsValidRevisionForBisect(bad_revision):
    raise NotBisectableError('Invalid "bad" revision: %s.' % bad_revision)

  test = _ChooseTest(anomalies, run_count)
  if not test or not can_bisect.IsValidTestForBisect(test.test_path):
    raise NotBisectableError('Could not select a test.')

  metric = start_try_job.GuessMetric(test.test_path)

  bisect_bot = start_try_job.GuessBisectBot(test.master_name, test.bot_name)
  if not bisect_bot or '_' not in bisect_bot:
    raise NotBisectableError('Could not select a bisect bot.')

  use_recipe = bool(start_try_job.GetBisectDirectorForTester(
      test.master_name, bisect_bot))

  new_bisect_config = start_try_job.GetBisectConfig(
      bisect_bot=bisect_bot,
      master_name=test.master_name,
      suite=test.suite_name,
      metric=metric,
      good_revision=good_revision,
      bad_revision=bad_revision,
      repeat_count=10,
      max_time_minutes=20,
      bug_id=bug_id,
      use_archive='true',
      use_buildbucket=use_recipe)

  if 'error' in new_bisect_config:
    raise NotBisectableError('Could not make a valid config.')

  config_python_string = utils.BisectConfigPythonString(new_bisect_config)

  bisect_job = try_job.TryJob(
      bot=bisect_bot,
      config=config_python_string,
      bug_id=bug_id,
      master_name=test.master_name,
      internal_only=test.internal_only,
      job_type='bisect',
      use_buildbucket=use_recipe)

  return bisect_job


def _IsBisectJobDueForRestart(bisect_job):
  """Whether bisect job is due for restart."""
  old_timestamp = (datetime.datetime.now() - datetime.timedelta(
      days=_BISECT_RESTART_PERIOD_DAYS[bisect_job.run_count - 1]))
  return bisect_job.last_ran_timestamp <= old_timestamp


def _ChooseTest(anomalies, index=0):
  """Chooses a test to use for a bisect job.

  The particular TestMetadata chosen determines the command and metric name that
  is chosen. The test to choose could depend on which of the anomalies has the
  largest regression size.

  Ideally, the choice of bisect bot to use should be based on bisect bot queue
  length, and the choice of metric should be based on regression size and noise
  level.

  However, we don't choose bisect bot and metric independently, since some
  regressions only happen for some tests on some platforms; we should generally
  only bisect with a given bisect bot on a given metric if we know that the
  regression showed up on that platform for that metric.

  Args:
    anomalies: A non-empty list of Anomaly entities.
    index: Index of the first Anomaly entity to look at. If this is greater
        than the number of Anomalies, it will wrap around. This is used to
        make it easier to get different suggestions for what test to use given
        the same list of alerts.

  Returns:
    A TestMetadata entity, or None if no valid TestMetadata could be chosen.
  """
  if not anomalies:
    return None
  index %= len(anomalies)
  anomalies.sort(cmp=_CompareAnomalyBisectability)
  for anomaly_entity in anomalies[index:]:
    if can_bisect.IsValidTestForBisect(
        utils.TestPath(anomaly_entity.GetTestMetadataKey())):
      return anomaly_entity.GetTestMetadataKey().get()
  return None


def _CompareAnomalyBisectability(a1, a2):
  """Compares two Anomalies to decide which Anomaly's TestMetadata is better to
     use.

  TODO(qyearsley): Take other factors into account:
   - Consider bisect bot queue length. Note: If there's a simple API to fetch
     this from build.chromium.org, that would be best; even if there is not,
     it would be possible to fetch the HTML page for the builder and check the
     pending list from that.
   - Prefer some platforms over others. For example, bisects on Linux may run
     faster; also, if we fetch info from build.chromium.org, we can check recent
     failures.
   - Consider test run time. This may not be feasible without using a list
     of approximate test run times for different test suites.
   - Consider stddev of test; less noise -> more reliable bisect.

  Args:
    a1: The first Anomaly entity.
    a2: The second Anomaly entity.

  Returns:
    Negative integer if a1 is better than a2, positive integer if a2 is better
    than a1, or zero if they're equally good.
  """
  if a1.percent_changed > a2.percent_changed:
    return -1
  elif a1.percent_changed < a2.percent_changed:
    return 1
  return 0


def _ChooseRevisionRange(anomalies):
  """Chooses a revision range to use for a bisect job.

  Note that the first number in the chosen revision range is the "last known
  good" revision, whereas the start_revision property of an Anomaly is the
  "first possible bad" revision.

  If the given set of anomalies is non-overlapping, the revision range chosen
  should be the intersection of the ranges.

  Args:
    anomalies: A non-empty list of Anomaly entities.

  Returns:
    A pair of revision numbers (good, bad), or (None, None) if no valid
    revision range can be chosen.

  Raises:
    NotBisectableError: A valid revision range could not be returned.
  """
  good_rev, good_test = max(
      (a.start_revision - 1, a.GetTestMetadataKey()) for a in anomalies)
  bad_rev, bad_test = min(
      (a.end_revision, a.GetTestMetadataKey()) for a in anomalies)
  if good_rev < bad_rev:
    good_rev = _GetRevisionForBisect(good_rev, good_test)
    bad_rev = _GetRevisionForBisect(bad_rev, bad_test)
    return (good_rev, bad_rev)
  raise NotBisectableError(
      'Good rev %s not smaller than bad rev %s.' % (good_rev, bad_rev))


def _GetRevisionForBisect(revision, test_key):
  """Gets a start or end revision value which can be used when bisecting.

  Note: This logic is parallel to that in elements/chart-container.html
  in the method getRevisionForBisect.

  Args:
    revision: The ID of a Row, not necessarily an actual revision number.
    test_key: The ndb.Key for a TestMetadata.

  Returns:
    An int or string value which can be used when bisecting.
  """
  row_parent_key = utils.GetTestContainerKey(test_key)
  row = graph_data.Row.get_by_id(revision, parent=row_parent_key)
  if row and hasattr(row, 'a_default_rev') and hasattr(row, row.a_default_rev):
    return getattr(row, row.a_default_rev)
  return revision


def _PrintStartedAndFailedBisectJobs():
  """Prints started and failed bisect jobs in datastore."""
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
