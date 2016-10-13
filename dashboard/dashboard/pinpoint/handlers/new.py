# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.api import taskqueue

from dashboard.common import request_handler
from dashboard.models import job_module


class NewHandler(request_handler.RequestHandler):

  def post(self):
    # TODO(dtu): Read the parameters from the request object.
    # Not doing it for now because it's easier to run tests this way.
    configuration = 'linux'
    test_suite = 'tab_switching.typical_25'
    test = 'http://www.airbnb.com/'
    metric = 'asdf'
    commits = (('chromium/src', 'a'), ('chromium/src', 'b'))

    # Validate parameters.
    if metric and not test_suite:
      raise ValueError("Specified a metric but there's no test_suite to run.")

    # Create job.
    commits = tuple(job_module.Commit(repository=repository, git_hash=git_hash)
                    for repository, git_hash in commits)
    job = job_module.Job(
        configuration=configuration,
        commits=commits,
        test_suite=test_suite,
        test=test,
        metric=metric)
    job_id = job.put().urlsafe()

    # Start job.
    task = taskqueue.add(queue_name='job-queue', target='pinpoint',
                         url='/run/' + job_id)
    job.task = task.name
    job.put()

    # Show status page.
    self.redirect('/job/' + job_id)
