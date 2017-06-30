# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import webapp2

from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import job as job_module


class New(webapp2.RequestHandler):
  """Handler that cooks up a fresh Pinpoint job."""

  def post(self):
    """Start a new Pinpoint job."""

    # TODO(dtu): Read the parameters from the request object.
    # Not doing it for now because it's easier to run tests this way.
    configuration = 'Mac Pro 10.11 Perf'
    test_suite = 'speedometer'
    test = None
    metric = None
    auto_explore = True
    bug_id = None

    change_1 = {
        'base_commit': {
            'repository': 'src',
            'git_hash': '2c1f8ed028edcb44c954cb2a0625a8f278933481',
        }
    }
    change_2 = {
        'base_commit': {
            'repository': 'src',
            'git_hash': '858ceafc7cf4f11a6549b8c1ace839a45d943d68',
        }
    }

    # Validate parameters.
    try:
      if metric and not test_suite:
        raise ValueError("Specified a metric but there's no test_suite to run.")
      changes = (change.Change.FromDict(change_1),
                 change.Change.FromDict(change_2))
    except (KeyError, ValueError) as e:
      self.response.set_status(400)
      self.response.write(e)
      return

    # Convert parameters to canonical internal representation.

    # Create job.
    job = job_module.Job.New(
        configuration=configuration,
        test_suite=test_suite,
        test=test,
        metric=metric,
        auto_explore=auto_explore,
        bug_id=bug_id)

    # Add changes.
    for c in changes:
      job.AddChange(c)

    # Put job into datastore.
    job_id = job.put().urlsafe()

    # Start job.
    job.Start()
    job.put()

    self.response.write(job_id)
