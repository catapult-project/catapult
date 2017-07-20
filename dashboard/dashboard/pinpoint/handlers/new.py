# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import webapp2

from dashboard.api import api_auth
from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job as job_module

_ERROR_METRIC_NO_TEST_SUITE = "Specified a metric but there's no test_suite "\
                              "to run."
_ERROR_BUG_ID = 'Bug ID must be integer value.'


class ParameterValidationError(Exception):
  pass


class New(webapp2.RequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def post(self):
    try:
      self._CreateJob()
    except (api_auth.ApiAuthException, ParameterValidationError) as e:
      self._WriteErrorMessage(e.message)

  def _WriteErrorMessage(self, message):
    self.response.out.write(json.dumps({'error': message}))

  @api_auth.Authorize
  def _CreateJob(self):
    """Start a new Pinpoint job."""
    configuration = self.request.get('configuration')
    test_suite = self.request.get('test_suite')
    test = self.request.get('test')
    metric = self.request.get('metric')
    auto_explore = self.request.get('auto_explore') == '1'
    bug_id = self._ValidateBugId(self.request.get('bug_id'))

    change_1 = {
        'base_commit': {
            'repository': self.request.get('start_repository'),
            'git_hash': self.request.get('start_git_hash')
        }
    }

    change_2 = {
        'base_commit': {
            'repository': self.request.get('end_repository'),
            'git_hash': self.request.get('end_git_hash')
        }
    }

    # Validate parameters.
    self._ValidateMetric(test_suite, metric)

    # Convert parameters to canonical internal representation.
    changes = self._ValidateChanges(change_1, change_2)

    # Create job.
    job = job_module.Job.New(
        configuration=configuration,
        test_suite=test_suite,
        test=test,
        metric=metric,
        auto_explore=auto_explore,
        bug_id=bug_id)

    # Add changes.
    for c in changes:
      job.AddChange(c)

    # Put job into datastore.
    job_id = job.put().urlsafe()

    # Start job.
    job.Start()
    job.put()

    self.response.out.write(json.dumps({
        'jobId': job_id,
        'jobUrl': job.url
    }))

  def _ValidateBugId(self, bug_id):
    if not bug_id:
      return None

    try:
      return int(bug_id)
    except ValueError:
      raise ParameterValidationError(_ERROR_BUG_ID)

  def _ValidateChanges(self, change_1, change_2):
    try:
      changes = (change.Change.FromDict(change_1),
                 change.Change.FromDict(change_2))
    except (KeyError, ValueError) as e:
      raise ParameterValidationError(str(e))

    return changes

  def _ValidateMetric(self, test_suite, metric):
    if metric and not test_suite:
      raise ParameterValidationError(_ERROR_METRIC_NO_TEST_SUITE)
