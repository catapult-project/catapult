# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from dashboard.api import api_request_handler
from dashboard.common import utils
from dashboard.pinpoint.models import job as job_module


class Cancel(api_request_handler.ApiRequestHandler):

  required_arguments = {'job_id', 'reason'}

  def _CheckUser(self):
    self._CheckIsLoggedIn()
    if not utils.IsTryjobUser():
      raise api_request_handler.ForbiddenError()

  def Post(self):
    # Pull out the Job ID and reason in the request.
    args = self.request.params.mixed()
    job_id = args.get('job_id')
    reason = args.get('reason')
    if not job_id or not reason:
      raise api_request_handler.BadRequestError()

    job = job_module.JobFromId(job_id)
    if not job:
      raise api_request_handler.NotFoundError()

    # Enforce first that only the users that started the job and administrators
    # can cancel jobs.
    email = utils.GetEmail()
    if not utils.IsAdministrator() and email != job.user:
      raise api_request_handler.ForbiddenError()

    # Truncate the reason down to 255 caracters including ellipses.
    job.Cancel(email, reason[:252] + '...' if len(reason) > 255 else reason)
    return {'job_id': job.job_id, 'state': 'Cancelled'}
