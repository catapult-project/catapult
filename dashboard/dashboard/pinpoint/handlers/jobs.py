# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides the web interface for displaying an overview of jobs."""

import json
import webapp2

from dashboard.pinpoint.models import job as job_module

_MAX_JOBS_TO_FETCH = 100
_MAX_JOBS_TO_COUNT = 1000


class Jobs(webapp2.RequestHandler):
  """Shows an overview of recent anomalies for perf sheriffing."""

  def post(self):
    result = self._GetJobs()

    self.response.out.write(json.dumps(result))

  def _GetJobs(self):
    job_future = job_module.Job.query().fetch_async(limit=_MAX_JOBS_TO_FETCH)
    count_future = job_module.Job.query().count_async(limit=_MAX_JOBS_TO_COUNT)

    result = {
        'jobs_list': [],
        'jobs_count': count_future.get_result(),
        'jobs_count_max': _MAX_JOBS_TO_COUNT
    }

    jobs = job_future.get_result()
    for job in jobs:
      result['jobs_list'].append(job.StatusDict())

    return result
