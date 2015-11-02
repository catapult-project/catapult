# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import webapp2

from perf_insights.endpoints.cloud_mapper import job_info


class StatusPage(webapp2.RequestHandler):

  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    jobid = self.request.get('jobid')

    job = job_info.JobInfo.get_by_id(jobid)
    status = 'ERROR'
    data = None
    if job:
      status = job.status
      if status == 'COMPLETE':
        data = job.results

    response = {
        'status': status,
        'data': data,
    }
    self.response.out.write(json.dumps(response))


app = webapp2.WSGIApplication([('/cloud_mapper/status', StatusPage)])
