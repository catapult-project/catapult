# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.pinpoint.models import job as job_module
from dashboard.common import utils

if utils.IsRunningFlask():
  from flask import make_response, request
else:
  import webapp2

if utils.IsRunningFlask():

  def JobHandlerGet(job_id):
    try:
      job = job_module.JobFromId(job_id)
    except ValueError:
      return make_response(
          json.dumps({'error': 'Invalid job id: %s' % job_id}), 400)

    if not job:
      return make_response(
          json.dumps({'error': 'Unknown job id: %s' % job_id}), 404)

    opts = request.args.getlist('o')
    return make_response(json.dumps(job.AsDict(opts)))
else:

  class Job(webapp2.RequestHandler):

    def get(self, job_id):
      # Validate parameters.
      try:
        job = job_module.JobFromId(job_id)
      except ValueError:
        self.response.set_status(400)
        self.response.write(json.dumps({'error': 'Invalid job id.'}))
        return

      if not job:
        self.response.set_status(404)
        self.response.write(json.dumps({'error': 'Unknown job id.'}))
        return

      opts = self.request.get_all('o')
      self.response.write(json.dumps(job.AsDict(opts)))
