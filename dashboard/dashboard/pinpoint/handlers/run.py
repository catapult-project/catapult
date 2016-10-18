# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from google.appengine.api import taskqueue

from dashboard.pinpoint.models import job as job_module


class RunHandler(webapp2.RequestHandler):
  """Handler for the Pinpoint job.

  This is our raison d'etre, folks. The thread that runs the job."""

  def post(self, job_id):
    job = job_module.JobFromId(job_id)

    # Get list of quests.
    # TODO: Define the quests.
    #quests = [quest.FindIsolated(job.configuration)]
    #if job.test_suite:
    #  quests.append(quest.RunTest(job.test_suite, job.test))
    #if job.metric:
    #  quests.append(quest.ReadTestResults(job.metric))

    # Run task.
    # TODO: Do.
    if True:
      return

    # Schedule moar task.
    task = taskqueue.add(queue_name='job-queue', target='pinpoint',
                         url='/run/' + job_id, countdown=60)
    job.task = task.name
    job.put()
