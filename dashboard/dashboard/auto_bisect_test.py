# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for auto_bisect module."""

import datetime
import unittest

import mock
import webapp2
import webtest

from dashboard import auto_bisect
from dashboard import testing_common
from dashboard.models import try_job


class MainTest(testing_common.TestCase):

  def setUp(self):
    super(MainTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/auto_bisect', auto_bisect.AutoBisectHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddTryJobs(self):
    """Adds a set of sample TryJob entities to the datastore."""
    now = datetime.datetime.now()
    try_job.TryJob(
        bug_id=111, status='failed', last_ran_timestamp=now, run_count=1).put()
    try_job.TryJob(
        bug_id=222, status='failed', last_ran_timestamp=now, run_count=2).put()
    try_job.TryJob(
        bug_id=333, status='failed', last_ran_timestamp=now,
        run_count=len(auto_bisect._BISECT_RESTART_PERIOD_DAYS) + 1).put()
    try_job.TryJob(
        bug_id=444, status='started', last_ran_timestamp=now,
        run_count=1).put()
    try_job.TryJob(
        bug_id=777, status='started', last_ran_timestamp=now,
        use_buildbucket=True, run_count=1).put()
    try_job.TryJob(
        bug_id=555, status=None, last_ran_timestamp=now, run_count=1).put()

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  def testPost_NoQueryParameters_RestartsBisects(self, mock_perform_bisect):
    self._AddTryJobs()
    self.testapp.post('/auto_bisect')
    mock_perform_bisect.assert_called_once_with(
        try_job.TryJob.query(try_job.TryJob.bug_id == 111).get())

  def testGet_WithStatsParameter_ListsTryJobs(self):
    self._AddTryJobs()
    response = self.testapp.get('/auto_bisect?stats')
    self.assertIn('Failed jobs: 3', response.body)
    self.assertIn('Started jobs: 2', response.body)


if __name__ == '__main__':
  unittest.main()
