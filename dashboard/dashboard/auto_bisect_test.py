# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test for auto_bisect module."""

import datetime
import sys
import unittest

import mock
import webapp2
import webtest

from dashboard import auto_bisect
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import try_job


class AutoBisectTest(testing_common.TestCase):

  def setUp(self):
    super(AutoBisectTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/auto_bisect', auto_bisect.AutoBisectHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  def testPost_FailedJobRunTwice_JobRestarted(self, mock_perform_bisect):
    testing_common.AddTests(
        ['ChromiumPerf'], ['linux-release'], {'sunspider': {'score': {}}})
    test_key = utils.TestKey('ChromiumPerf/linux-release/sunspider/score')
    anomaly.Anomaly(
        bug_id=111, test=test_key,
        start_revision=300100, end_revision=300200,
        median_before_anomaly=100, median_after_anomaly=200).put()
    try_job.TryJob(
        bug_id=111, status='failed',
        last_ran_timestamp=datetime.datetime.now() - datetime.timedelta(days=8),
        run_count=2).put()
    self.testapp.post('/auto_bisect')
    mock_perform_bisect.assert_called_once_with(
        try_job.TryJob.query(try_job.TryJob.bug_id == 111).get())

  @unittest.skipIf(sys.platform.startswith('win'), 'Flaky on Windows (#1285)')
  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  def testPost_FailedJobRunOnce_JobRestarted(self, mock_perform_bisect):
    try_job.TryJob(
        bug_id=222, status='failed',
        last_ran_timestamp=datetime.datetime.now(),
        run_count=1).put()
    self.testapp.post('/auto_bisect')
    mock_perform_bisect.assert_called_once_with(
        try_job.TryJob.query(try_job.TryJob.bug_id == 222).get())

  @mock.patch.object(auto_bisect.start_try_job, 'LogBisectResult')
  def testPost_JobRunTooManyTimes_LogsMessage(self, mock_log_result):
    job_key = try_job.TryJob(
        bug_id=333, status='failed',
        last_ran_timestamp=datetime.datetime.now(),
        run_count=len(auto_bisect._BISECT_RESTART_PERIOD_DAYS)+1).put()
    self.testapp.post('/auto_bisect')
    self.assertIsNone(job_key.get())
    mock_log_result.assert_called_once_with(333, mock.ANY)

  def testGet_WithStatsParameter_ListsTryJobs(self):
    now = datetime.datetime.now()
    try_job.TryJob(
        bug_id=222, status='failed',
        last_ran_timestamp=now, run_count=2).put()
    try_job.TryJob(
        bug_id=444, status='started',
        last_ran_timestamp=now, run_count=1).put()
    try_job.TryJob(
        bug_id=777, status='started',
        last_ran_timestamp=now, use_buildbucket=True, run_count=1).put()
    try_job.TryJob(
        bug_id=555, status=None,
        last_ran_timestamp=now, run_count=1).put()
    response = self.testapp.get('/auto_bisect?stats')
    self.assertIn('Failed jobs: 1', response.body)
    self.assertIn('Started jobs: 2', response.body)


class StartNewBisectForBugTest(testing_common.TestCase):

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  def testStartNewBisectForBug_StartsBisect(self, mock_perform_bisect):
    testing_common.AddTests(
        ['ChromiumPerf'], ['linux-release'], {'sunspider': {'score': {}}})
    test_key = utils.TestKey('ChromiumPerf/linux-release/sunspider/score')
    anomaly.Anomaly(
        bug_id=111, test=test_key,
        start_revision=300100, end_revision=300200,
        median_before_anomaly=100, median_after_anomaly=200).put()
    auto_bisect.StartNewBisectForBug(111)
    job = try_job.TryJob.query(try_job.TryJob.bug_id == 111).get()
    mock_perform_bisect.assert_called_once_with(job)

  def testStartNewBisectForBug_RevisionTooLow_ReturnsError(self):
    testing_common.AddTests(
        ['ChromiumPerf'], ['linux-release'], {'sunspider': {'score': {}}})
    test_key = utils.TestKey('ChromiumPerf/linux-release/sunspider/score')
    anomaly.Anomaly(
        bug_id=222, test=test_key,
        start_revision=1200, end_revision=1250,
        median_before_anomaly=100, median_after_anomaly=200).put()
    result = auto_bisect.StartNewBisectForBug(222)
    self.assertEqual({'error': 'Invalid "good" revision: 1199.'}, result)

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  def testStartNewBisectForBug_WithDefaultRevs_StartsBisect(
      self, mock_perform_bisect):
    testing_common.AddTests(
        ['ChromiumPerf'], ['linux-release'], {'sunspider': {'score': {}}})
    test_key = utils.TestKey('ChromiumPerf/linux-release/sunspider/score')
    testing_common.AddRows(
        'ChromiumPerf/linux-release/sunspider/score',
        {
            1199: {
                'a_default_rev': 'r_foo',
                'r_foo': '9e29b5bcd08357155b2859f87227d50ed60cf857'
            },
            1250: {
                'a_default_rev': 'r_foo',
                'r_foo': 'fc34e5346446854637311ad7793a95d56e314042'
            }
        })
    anomaly.Anomaly(
        bug_id=333, test=test_key,
        start_revision=1200, end_revision=1250,
        median_before_anomaly=100, median_after_anomaly=200).put()
    auto_bisect.StartNewBisectForBug(333)
    job = try_job.TryJob.query(try_job.TryJob.bug_id == 333).get()
    mock_perform_bisect.assert_called_once_with(job)

  def testStartNewBisectForBug_UnbisectableTest_ReturnsError(self):
    testing_common.AddTests(['V8'], ['x86'], {'v8': {'sunspider': {}}})
    # The test suite "v8" is in the black-list of test suite names.
    test_key = utils.TestKey('V8/x86/v8/sunspider')
    anomaly.Anomaly(
        bug_id=444, test=test_key,
        start_revision=155000, end_revision=155100,
        median_before_anomaly=100, median_after_anomaly=200).put()
    result = auto_bisect.StartNewBisectForBug(444)
    self.assertEqual({'error': 'Could not select a test.'}, result)


if __name__ == '__main__':
  unittest.main()
