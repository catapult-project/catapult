# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import webapp2

from google.appengine.api import taskqueue
from perf_insights.endpoints.cloud_mapper import job_info


class CancelPage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'

    jobid = self.request.get('jobid')
    job = job_info.JobInfo.get_by_id(jobid)
    if not job:
      response = {'success': False}
      self.response.out.write(json.dumps(response))
      return

    taskqueue.Queue('mapper-queue').delete_tasks_by_name(job.running_tasks)
    job.status = 'CANCELLED'
    job.put()

    response = {'success': True}
    self.response.out.write(json.dumps(response))

app = webapp2.WSGIApplication([('/cloud_mapper/cancel', CancelPage)])
