# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from dashboard.pinpoint.models import job as job_module


class RunHandler(webapp2.RequestHandler):
  """Handler that runs a Pinpoint job."""

  def post(self, job_id):
    job = job_module.JobFromId(job_id)
    job.Run()
    job.put()
