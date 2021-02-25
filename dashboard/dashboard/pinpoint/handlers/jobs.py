# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides the web interface for displaying an overview of jobs."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import json
import webapp2

from dashboard.pinpoint.models import job as job_module
from dashboard.common import utils

_MAX_JOBS_TO_FETCH = 100
_MAX_JOBS_TO_COUNT = 1000


class Jobs(webapp2.RequestHandler):
  """Shows an overview of recent anomalies for perf sheriffing."""

  def get(self):
    self.response.out.write(
        json.dumps(
            _GetJobs(self.request.get_all('o'),
                     self.request.get_all('filter'))))


def _GetJobs(options, query_filter):
  query = job_module.Job.query()

  # Query filters should a string as described in https://google.aip.dev/160
  # For now we only support filtering on user, so we'll look for the 'user='
  # field in the string.
  for f in query_filter:
    if f.startswith('user='):
      query = query.filter(job_module.Job.user == f[len('user='):])

  query = query.order(-job_module.Job.created)
  job_future = query.fetch_async(limit=_MAX_JOBS_TO_FETCH)
  count_future = query.count_async(limit=_MAX_JOBS_TO_COUNT)

  result = {
      'jobs': [],
      'count': count_future.get_result(),
      'max_count': _MAX_JOBS_TO_COUNT
  }

  jobs = job_future.get_result()

  def _FixupEmails(j):
    if 'user' not in j:
      return j
    email = j['user']
    if email == utils.ServiceAccountEmail():
      email = 'chromeperf (automation)'
    logging.debug('email = %s', email)
    j['user'] = email
    return j

  for job in jobs:
    result['jobs'].append(_FixupEmails(job.AsDict(options)))

  return result
