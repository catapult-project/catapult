# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job as job_module
from dashboard.services import gitiles_service


class NewHandler(webapp2.RequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def post(self):
    # TODO(dtu): Read the parameters from the request object.
    # Not doing it for now because it's easier to run tests this way.
    configuration = 'Mac Pro 10.11 Perf'
    test_suite = 'speedometer'
    test = None
    metric = None
    commits = (('chromium/src', '2c1f8ed028edcb44c954cb2a0625a8f278933481'),
               ('chromium/src', '858ceafc7cf4f11a6549b8c1ace839a45d943d68'),)

    # Validate parameters.
    if metric and not test_suite:
      raise ValueError("Specified a metric but there's no test_suite to run.")

    # Validate commit hashes.
    for repository, git_hash in commits:
      try:
        gitiles_service.CommitInfo(repository, git_hash)
      except gitiles_service.NotFoundError:
        raise ValueError('Could not find the commit with Gitiles: %s@%s' %
                         (repository, git_hash))

    # Convert parameters to canonical internal representation.

    # Create job.
    job = job_module.Job.New(
        configuration=configuration,
        test_suite=test_suite,
        test=test,
        metric=metric,
        auto_explore=True)

    # Add changes.
    for repository, git_hash in commits:
      job.AddChange(change.Change(change.Dep(repository, git_hash)))

    # Put job into datastore.
    job_id = job.put().urlsafe()

    # Start job.
    job.Start()
    job.put()

    # Show status page.
    # TODO: Should return a JSON result instead. Use Cloud Endpoints.
    self.redirect('/job/' + job_id)
