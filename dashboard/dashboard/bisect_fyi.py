# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for a cron job to run bisects integration tests."""

import datetime
import logging
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
  use_recipe = bool(start_try_job.GetBisectDirectorForTester(bisect_bot))
  bisect_job = try_job.TryJob(
      bot=bisect_bot,
      config=config_python_string,
      bug_id=bisect_config.get('bug_id', -1),
      master_name='ChromiumPerf',
      job_type='bisect-fyi',
      use_buildbucket=use_recipe,
      job_name=test_name)

  return bisect_job


def VerifyBisectFYIResults(job, bisect_results):
  """Verifies the bisect results against expected results in test config."""
  bisect_fyi_configs = stored_object.Get(_BISECT_FYI_CONFIGS_KEY)
  for test_name, config in bisect_fyi_configs.iteritems():
    if job.job_name == test_name:
      errors = _VerifyExpectedResults(
          bisect_results.get('results'), config.get('expected_results'))
      if errors:
        bisect_results['status'] = 'Failure'
        bisect_results['errors'] = errors
  return bisect_results


def VerifyBugUpdate(job, issue_tracker, bisect_results):
  """Verifies whether bug is updated with the bisect results."""
  comment_info = issue_tracker.GetLastBugCommentsAndTimestamp(job.bug_id)
  err_msg = 'Failed to update bug %s with bisect results.' % job.bug_id
  if not comment_info:
    bisect_results['status'] = 'Failure'
    if bisect_results.get('errors'):
      err_msg = '%s\n%s' % (bisect_results['errors'], err_msg)
    bisect_results['errors'] = err_msg
    return bisect_results

  bug_update_timestamp = datetime.datetime.strptime(
      comment_info['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
  try_job_timestamp = time.mktime(job.last_ran_timestamp.timetuple())
  if bug_update_timestamp <= try_job_timestamp:
    logging.info('Issue updated timestamp: %s', bug_update_timestamp)
    logging.info('Try job timestamp: %s', try_job_timestamp)
    bisect_results['status'] = 'Failure'
    if bisect_results.get('errors'):
      err_msg = '%s\n%s' % (bisect_results['errors'], err_msg)
    bisect_results['errors'] = err_msg
  return bisect_results


def _VerifyExpectedResults(bisect_results, expected_results):
  if not expected_results:
    return 'No expected results found in test config.'
  error_list = []
  for key, value in expected_results.iteritems():
    if value not in bisect_results:
      error_list.append('Expected results %s = "%s" not found in bisect '
                        'results.\n' % (key, value))

  return ''.join(error_list)


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
      to='auto-bisect-team@google.com',
      subject='[Bisect FYI Alert]Failed to run bisect integration tests.',
      body=_TextBody(errors_list))
