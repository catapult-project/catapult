# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to record bad bisect."""

import json

from google.appengine.api import users

from dashboard import quick_logger
from dashboard.common import request_handler
from dashboard.common import utils
from dashboard.common import xsrf
from dashboard.models import try_job

SUCCESS_CONFIRMED = 'Confirmed bad bisect.  Thank you for reporting.'

ERROR_NO_TRYJOB = 'No try_job_id specified.'
ERROR_TRYJOB_DOES_NOT_EXIST = 'TryJob does not exist.'
ERROR_TRYJOB_INVALID = 'TryJob id is invalid.'
ERROR_INVALID_USER = \
"""User "%s" not authorized. You must be logged in with a chromium account"""


class BadBisectHandler(request_handler.RequestHandler):

  def get(self):
    """Renders bad_bisect.html."""
    if self.request.get('list'):
      self.response.out.write(json.dumps(_GetRecentFeedback()))
    else:
      self.RenderStaticHtml('bad_bisect.html')

  def post(self):
    """Handles post requests from bad_bisect.html."""
    user = users.get_current_user()
    if not utils.IsValidSheriffUser():
      message = ERROR_INVALID_USER % user
      self.response.out.write(json.dumps({'error': message}))
      return

    if not self.request.get('try_job_id'):
      self.response.out.write(json.dumps({'error': ERROR_NO_TRYJOB}))
      return

    try:
      try_job_id = int(self.request.get('try_job_id'))
      job = try_job.TryJob.get_by_id(try_job_id)
      if not job:
        self.response.out.write(
            json.dumps({'error': ERROR_TRYJOB_DOES_NOT_EXIST}))
        return

      # If there's a token, they're confirming they want to flag this bisect.
      if self.request.get('xsrf_token'):
        self._ConfirmBadBisect(user, job, try_job_id)
        return

      values = {}
      self.GetDynamicVariables(values)
      self.response.out.write(json.dumps(values))

    except ValueError:
      self.response.out.write(json.dumps({'error': ERROR_TRYJOB_INVALID}))
      return

  @xsrf.TokenRequired
  def _ConfirmBadBisect(self, user, job, try_job_id):
    user = users.get_current_user()
    email = user.email()
    if not job.bad_result_emails:
      job.bad_result_emails = set()
    if email not in job.bad_result_emails:
      job.bad_result_emails.add(email)
      job.put()
      _LogFeedback(try_job_id, email)

    values = {'headline': SUCCESS_CONFIRMED}
    self.response.out.write(json.dumps(values))


def _LogFeedback(try_job_id, email):
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('bad_bisect', 'report', formatter)
  message = '%s marked try job %d.' % (email, try_job_id)
  logger.Log(message)
  logger.Save()


def _GetRecentFeedback():
  jobs = try_job.TryJob.query().fetch()
  results = []
  for job in jobs:
    if not job.bad_result_emails:
      continue
    results.append({
        'bad_result_emails': list(job.bad_result_emails),
        'try_job_id': job.key.id(),
        'status': job.results_data.get('status'),
        'buildbot_log_url': job.results_data.get('buildbot_log_url'),
        'bug_id': job.results_data.get('bug_id'),
        'score': job.results_data.get('score'),
    })
  return results
