# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to run bisects integration tests."""

import datetime
import time

from google.appengine.api import mail

from dashboard import auto_bisect
from dashboard import datastore_hooks
from dashboard import request_handler
from dashboard import start_try_job
from dashboard import stored_object
from dashboard import utils
from dashboard.models import try_job

_BISECT_FYI_CONFIGS_KEY = 'bisect_fyi_config_map'
_TEST_FAILURE_TEMPLATE = """
  Test Name: %(test_name)s
  Error:%(error)s
  Bisect Config: %(info)s
"""


class BisectFYIHandler(request_handler.RequestHandler):
  """URL endpoint for a cron job to run bisects integration tests."""

  def get(self):
    """A get request is the same a post request for this endpoint."""
    self.post()

  def post(self):
    """Runs auto bisects."""
    datastore_hooks.SetPrivilegedRequest()
    _RunBisectIntegrationTests()


def _RunBisectIntegrationTests():
  """Runs bisect jobs with pre determined configs."""
  errors_list = {}
  bisect_fyi_configs = stored_object.Get(_BISECT_FYI_CONFIGS_KEY)
  for test_name, config in bisect_fyi_configs.iteritems():
    if config.get('bisect_config'):
      results = _StartBisectFYIJob(test_name, config.get('bisect_config'))
      if 'error' in results:
        errors_list[test_name] = {
            'error': results['error'],
            'info': config.get('bisect_config')}
    else:
      errors_list[test_name] = {'error': 'Missing bisect config.'}
  if errors_list:
    _SendEmailAlert(errors_list)


def _StartBisectFYIJob(test_name, bisect_config):
  """Re-starts a bisect-job after modifying it's config based on run count.

  Args:
    test_name: Name of the test case.
    bisect_job: TryJob entity with initialized bot name and config.

  Returns:
    If successful, a dict containing "issue_id" and "issue_url" for the
    bisect job. Otherwise, a dict containing "error", with some description
    of the reason why a job wasn't started.
  """
  try:
    bisect_job = _MakeBisectFYITryJob(test_name, bisect_config)
  except auto_bisect.NotBisectableError as e:
    return {'error': e.message}
  try:
    bisect_result = start_try_job.PerformBisect(bisect_job)
  except request_handler.InvalidInputError as e:
    bisect_result = {'error': e.message}
  if 'error' in bisect_result:
    if bisect_job.key:
      bisect_job.key.delete()
  return bisect_result


def _MakeBisectFYITryJob(test_name, bisect_config):
  """Creates a TryJob entity with the bisect config.

  Args:
    test_name: Name of the test case.
    bisect_config: A dictionary of parameters for a bisect job.

  Returns:
    A TryJob entity, which has not yet been put in the datastore.

  Raises:
    NotBisectableError: A valid bisect config could not be created.
  """
  bisect_bot = bisect_config.get('recipe_tester_name')
  if not bisect_bot:
    raise auto_bisect.NotBisectableError('Could not select a bisect bot.')

  config_python_string = utils.BisectConfigPythonString(bisect_config)
  use_recipe = bool(start_try_job.GetBisectDirectorForTester(
      bisect_config.get('master_name', 'ChromiumPerf'), bisect_bot))
  bisect_job = try_job.TryJob(
      bot=bisect_bot,
      config=config_python_string,
      bug_id=bisect_config.get('bug_id', -1),
      master_name=bisect_config.get('master_name', 'ChromiumPerf'),
      job_type='bisect-fyi',
      use_buildbucket=use_recipe,
      job_name=test_name)

  return bisect_job


def VerifyBisectFYIResults(job):
  """Verifies the bisect results against expected results in test config.

  Args:
    job: TryJob entity.

  Returns:
    A message with the missing properties, otherwise returns an empty string.
  """
  expected_results = _GetBisectConfig(job).get('expected_results')
  try:
    utils.Validate(expected_results, job.results_data)
  except ValueError as e:
    return 'Bisect result is not as expected: %s.' % e
  return ''


def IsBugUpdated(job, issue_tracker):
  """Verifies whether bug is updated with the bisect results."""
  comment_info = issue_tracker.GetLastBugCommentsAndTimestamp(job.bug_id)
  if not comment_info:
    return False

  last_comment_timestamp = datetime.datetime.strptime(
      comment_info['timestamp'], '%Y-%m-%dT%H:%M:%S')
  bug_update_timestamp = time.mktime(last_comment_timestamp.timetuple())
  try_job_timestamp = time.mktime(job.last_ran_timestamp.timetuple())

  if bug_update_timestamp <= try_job_timestamp:
    return False
  return True


def _TextBody(errors_list):
  """Returns the text body for an email about test failures."""
  test_alerts = []
  for test_name, data in errors_list.iteritems():
    test_alerts.append(
        _TEST_FAILURE_TEMPLATE % {
            'test_name': test_name,
            'error': data.get('error'),
            'info': data.get('info', '')
        }
    )
  return '.\n'.join(test_alerts)


def _SendEmailAlert(errors_list):
  """Sends email alert about bisect integration tests failures."""
  mail.send_mail(
      sender='gasper-alerts@google.com',
      to='chrome-performance-monitoring-alerts@google.com',
      subject='[Bisect FYI Alert]Failed to run bisect integration tests.',
      body=_TextBody(errors_list))


def _GetBisectConfig(job):
  bisect_fyi_configs = stored_object.Get(_BISECT_FYI_CONFIGS_KEY)
  for test_name, config in bisect_fyi_configs.iteritems():
    if job.job_name == test_name:
      return config
  return {}
