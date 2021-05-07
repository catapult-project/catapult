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
_DEFAULT_FILTERED_JOBS = 40


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
  # We implement a simple parser for the query_filter provided, to allow us to
  # support a simple expression language expressed in the AIP.
  # FIXME: Implement a validating parser.
  def _ParseExpressions():
    # Yield tokens as we parse them.
    # We only support 'AND' as a keyword and ignore any 'OR's.
    for q in query_filter:
      parts = q.split(' ')
      for p in parts:
        if p == 'AND':
          continue
        yield p

  has_filter = False
  for f in _ParseExpressions():
    if f.startswith('user='):
      has_filter = True
      query = query.filter(job_module.Job.user == f[len('user='):])
    elif f.startswith('configuration='):
      has_filter = True
      query = query.filter(
          job_module.Job.configuration == f[len('configuration='):])
    elif f.startswith('comparison_mode='):
      has_filter = True
      query = query.filter(
          job_module.Job.comparison_mode == f[len('comparison_mode='):])

  query = query.order(-job_module.Job.created)
  limit = _MAX_JOBS_TO_FETCH if not has_filter else _DEFAULT_FILTERED_JOBS
  job_future = query.fetch_async(limit=limit)
  count_future = query.count_async(limit=_MAX_JOBS_TO_COUNT)

  result = {
      'jobs': [],
      'count': count_future.get_result(),
      'max_count': _MAX_JOBS_TO_COUNT
  }

  jobs = job_future.get_result()
  service_account_email = utils.ServiceAccountEmail()
  logging.debug('service account email = %s', service_account_email)

  def _FixupEmails(j):
    user = j.get('user')
    if user and user == service_account_email:
      j['user'] = 'chromeperf (automation)'
    return j

  for job in jobs:
    result['jobs'].append(_FixupEmails(job.AsDict(options)))

  return result
