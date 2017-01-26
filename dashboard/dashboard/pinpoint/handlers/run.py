# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import taskqueue

from dashboard.pinpoint.models import job as job_module


# We want this to be fast to minimize overhead while waiting for tasks to
# finish, but don't want to consume too many resources.
_TASK_INTERVAL = 10


class RunHandler(webapp2.RequestHandler):
  """Handler that runs a Pinpoint job."""

  def post(self, job_id):
    job = job_module.JobFromId(job_id)

    # Run!
    if job.auto_explore:
      job.Explore()
    work_left = job.ScheduleWork()

    # Schedule moar task.
    if work_left:
      task = taskqueue.add(queue_name='job-queue', target='pinpoint',
                           url='/run/' + job_id, countdown=_TASK_INTERVAL)
      job.task = task.name

    # Update the datastore.
    job.put()
