# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import webapp2

from google.appengine.api.taskqueue import TaskRetryOptions
from google.appengine.ext import deferred

from dashboard.common import layered_cache
from dashboard.pinpoint.models import job as job_module


_JOB_CACHE_KEY = 'pinpoint_refresh_jobs_%s'
_JOB_MAX_RETRIES = 3
_JOB_FROZEN_THRESHOLD = datetime.timedelta(hours=6)
_FAILURE_MESSAGE = ('An unknown failure occurred during the run.\n'\
    'Please file a bug under Speed>Bisection with this job.')


class RefreshJobs(webapp2.RequestHandler):
  def get(self):
    _FindAndRestartJobs()


def _FindFrozenJobs():
  q = job_module.Job.query()
  q = q.filter(job_module.Job.completed == False)

  jobs = q.fetch()

  now = datetime.datetime.now()

  def _IsFrozen(j):
    time_elapsed = now - j.updated
    return time_elapsed >= _JOB_FROZEN_THRESHOLD

  results = [j for j in jobs if _IsFrozen(j)]
  return results


def _FindAndRestartJobs():
  jobs = _FindFrozenJobs()
  opts = TaskRetryOptions(task_retry_limit=1)

  for j in jobs:
    deferred.defer(_ProcessFrozenJob, j.job_id, _retry_options=opts)


def _ProcessFrozenJob(job_id):
  job = job_module.JobFromId(job_id)
  key = _JOB_CACHE_KEY % job_id
  info = layered_cache.Get(key)
  if not info:
    info = {'retries': 0}

  if info.get('retries') == _JOB_MAX_RETRIES:
    info['retries'] += 1
    layered_cache.Set(key, info, days_to_keep=30)
    job.Fail(_FAILURE_MESSAGE)
    job.put()
    return
  elif info.get('retries') > _JOB_MAX_RETRIES:
    return

  info['retries'] += 1
  layered_cache.Set(key, info, days_to_keep=30)

  job._Schedule()
  job.put()
