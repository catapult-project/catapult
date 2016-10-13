# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.common import request_handler
from dashboard.models import job_module


class StatusHandler(request_handler.RequestHandler):

  def get(self, job_id):
    job = job_module.JobFromId(job_id)
    # TODO: Generate an excellent Polymer UI.
    del job

  def post(self):
    pass  # TODO: Allow modifications to the job.
