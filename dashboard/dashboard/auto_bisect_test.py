# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import mock
import webapp2
import webtest

from dashboard import auto_bisect
from dashboard import namespaced_stored_object
from dashboard import request_handler
from dashboard import start_try_job
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import try_job


@mock.patch.object(utils, 'TickMonitoringCustomMetric', mock.MagicMock())
class AutoBisectTest(testing_common.TestCase):

  def setUp(self):
    super(AutoBisectTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/auto_bisect', auto_bisect.AutoBisectHandler)])
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('internal@chromium.org')
    namespaced_stored_object.Set(
        start_try_job._TESTER_DIRECTOR_MAP_KEY,
        {
            'ChromiumPerf': {
                'linux_perf_tester': 'linux_perf_bisector',
                'win64_nv_tester': 'linux_perf_bisector',
            }
        })

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
        run_count=len(auto_bisect._BISECT_RESTART_PERIOD_DAYS) + 1).put()
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

  def setUp(self):
    super(StartNewBisectForBugTest, self).setUp()
    self.SetCurrentUser('internal@chromium.org')
    namespaced_stored_object.Set(
        start_try_job._TESTER_DIRECTOR_MAP_KEY,
        {
            'ChromiumPerf': {
                'linux_perf_tester': 'linux_perf_bisector',
                'win64_nv_tester': 'linux_perf_bisector',
            }
        })

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

  @mock.patch.object(
      auto_bisect.start_try_job, 'PerformBisect',
      mock.MagicMock(side_effect=request_handler.InvalidInputError(
          'Some reason')))
  def testStartNewBisectForBug_InvalidInputErrorRaised_ReturnsError(self):
    testing_common.AddTests(['Foo'], ['bar'], {'sunspider': {'score': {}}})
    test_key = utils.TestKey('Foo/bar/sunspider/score')
    anomaly.Anomaly(
        bug_id=345, test=test_key,
        start_revision=300100, end_revision=300200,
        median_before_anomaly=100, median_after_anomaly=200).put()
    result = auto_bisect.StartNewBisectForBug(345)
    self.assertEqual({'error': 'Some reason'}, result)

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


class TickMonitoringCustomMetricTest(testing_common.TestCase):

  def setUp(self):
    super(TickMonitoringCustomMetricTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/auto_bisect', auto_bisect.AutoBisectHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch.object(utils, 'TickMonitoringCustomMetric')
  def testPost_NoTryJobs_CustomMetricTicked(self, mock_tick):
    self.testapp.post('/auto_bisect')
    mock_tick.assert_called_once_with('RestartFailedBisectJobs')

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  @mock.patch.object(utils, 'TickMonitoringCustomMetric')
  def testPost_RunCount1_ExceptionInPerformBisect_CustomMetricNotTicked(
      self, mock_tick, mock_perform_bisect):
    mock_perform_bisect.side_effect = request_handler.InvalidInputError()
    try_job.TryJob(
        bug_id=222, status='failed',
        last_ran_timestamp=datetime.datetime.now(),
        run_count=1).put()
    self.testapp.post('/auto_bisect')
    self.assertEqual(0, mock_tick.call_count)

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  @mock.patch.object(utils, 'TickMonitoringCustomMetric')
  def testPost_RunCount2_ExceptionInPerformBisect_CustomMetricNotTicked(
      self, mock_tick, mock_perform_bisect):
    mock_perform_bisect.side_effect = request_handler.InvalidInputError()
    try_job.TryJob(
        bug_id=111, status='failed',
        last_ran_timestamp=datetime.datetime.now() - datetime.timedelta(days=8),
        run_count=2).put()
    self.testapp.post('/auto_bisect')
    self.assertEqual(0, mock_tick.call_count)

  @mock.patch.object(auto_bisect.start_try_job, 'PerformBisect')
  @mock.patch.object(utils, 'TickMonitoringCustomMetric')
  def testPost_NoExceptionInPerformBisect_CustomMetricTicked(
      self, mock_tick, mock_perform_bisect):
    try_job.TryJob(
        bug_id=222, status='failed',
        last_ran_timestamp=datetime.datetime.now(),
        run_count=1).put()
    self.testapp.post('/auto_bisect')
    self.assertEqual(1, mock_perform_bisect.call_count)
    mock_tick.assert_called_once_with('RestartFailedBisectJobs')


if __name__ == '__main__':
  unittest.main()
