# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint to record bad bisect."""

import json

from google.appengine.api import users
from google.appengine.ext.webapp import util

from dashboard import quick_logger
from dashboard import request_handler
from dashboard import utils
from dashboard import xsrf
from dashboard.models import try_job


class BadBisectHandler(request_handler.RequestHandler):

  def get(self):
    """Renders bad_bisect.html."""
    if self.request.get('list'):
      self.response.out.write(_PrintRecentFeedback())
      return
    self._RenderForm()

  @util.login_required
  def _RenderForm(self):
    if not utils.IsValidSheriffUser():
      self._RenderError('No permission.')
      return
    if not self.request.get('try_job_id'):
      self._RenderError('Missing try_job_id.')
      return

    self.RenderHtml('bad_bisect.html',
                    {'try_job_id': self.request.get('try_job_id')})

  @xsrf.TokenRequired
  def post(self):
    """Handles post requests from bad_bisect.html."""
    if not utils.IsValidSheriffUser():
      self._RenderError('No permission.')
      return
    if not self.request.get('try_job_id'):
      self._RenderError('Missing try_job_id.')
      return

    try_job_id = int(self.request.get('try_job_id'))
    job = try_job.TryJob.get_by_id(try_job_id)
    if not job:
      self._RenderError('TryJob doesn\'t exist.')
      return

    user = users.get_current_user()
    email = user.email()
    if not job.bad_result_emails:
      job.bad_result_emails = set()
    if email not in job.bad_result_emails:
      job.bad_result_emails.add(email)
      job.put()
      _LogFeedback(try_job_id, email)

    self.RenderHtml('result.html', {
        'headline': 'Confirmed bad bisect.  Thank you for reporting.'})

  def _RenderError(self, error):
    self.RenderHtml('result.html', {'errors': [error]})


def _LogFeedback(try_job_id, email):
  formatter = quick_logger.Formatter()
  logger = quick_logger.QuickLogger('bad_bisect', 'report', formatter)
  message = '%s marked try job %d.' % (email, try_job_id)
  logger.Log(message)
  logger.Save()

def _PrintRecentFeedback():
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
  return json.dumps(results)
