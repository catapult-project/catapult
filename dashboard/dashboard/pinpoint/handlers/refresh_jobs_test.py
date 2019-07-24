# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import logging
import mock
import sys

from dashboard.common import layered_cache
from dashboard.pinpoint.handlers import refresh_jobs
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint import test


class RefreshJobsTest(test.TestCase):

  def setUp(self):
    # Intercept the logging messages, so that we can see them when we have test
    # output in failures.
    self.logger = logging.getLogger()
    self.logger.level = logging.DEBUG
    self.stream_handler = logging.StreamHandler(sys.stdout)
    self.logger.addHandler(self.stream_handler)
    self.addCleanup(self.logger.removeHandler, self.stream_handler)
    super(RefreshJobsTest, self).setUp()

  def testGet(self):
    job = job_module.Job.New((), ())
    job.task = '123'
    job.started = True
    job.updated = datetime.datetime.utcnow() - datetime.timedelta(hours=8)
    job.put()
    job._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    job.Fail = mock.MagicMock()  # pylint: disable=invalid-name
    self.assertTrue(job.running)
    self.testapp.get('/cron/refresh-jobs')
    self.ExecuteDeferredTasks('default')
    self.assertTrue(job._Schedule.called)
    self.assertFalse(job.Fail.called)

  def testGetWithQueuedJobs(self):
    queued_job = job_module.Job.New((), ())
    queued_job._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    queued_job.Fail = mock.MagicMock()  # pylint: disable=invalid-name
    running_job = job_module.Job.New((), ())
    running_job.task = '123'
    running_job.started = True
    running_job.updated = datetime.datetime.utcnow() - datetime.timedelta(
        hours=24)
    running_job.put()
    running_job._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    running_job.Fail = mock.MagicMock()  # pylint: disable=invalid-name
    self.assertFalse(queued_job.running)
    self.assertTrue(running_job.running)
    self.testapp.get('/cron/refresh-jobs')
    self.ExecuteDeferredTasks('default')
    self.assertFalse(queued_job._Schedule.called)
    self.assertTrue(running_job._Schedule.called)

  def testGetWithCancelledJobs(self):
    cancelled_job = job_module.Job.New((), ())
    cancelled_job._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    cancelled_job.Fail = mock.MagicMock()  # pylint: disable=invalid-name
    cancelled_job.started = True
    cancelled_job.updated = datetime.datetime.utcnow() - datetime.timedelta(
        hours=24)
    cancelled_job.cancelled = True
    cancelled_job.cancel_reason = 'Testing cancellation!'
    cancelled_job.put()
    self.assertFalse(cancelled_job.running)
    self.testapp.get('/cron/refresh-jobs')
    self.ExecuteDeferredTasks('default')
    self.assertFalse(cancelled_job._Schedule.called)
    self.assertFalse(cancelled_job.Fail.called)

  def testGet_RetryLimit(self):
    j1 = job_module.Job.New((), ())
    j1.task = '123'
    j1.started = True
    j1.put()
    j1._Schedule = mock.MagicMock()
    j1.Fail = mock.MagicMock()

    j2 = job_module.Job.New((), ())
    j2.task = '123'
    j2.started = True
    j2.updated = datetime.datetime.utcnow() - datetime.timedelta(hours=8)
    j2.put()
    j2._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    j2.Fail = mock.MagicMock()  # pylint: disable=invalid-name

    layered_cache.Set(refresh_jobs._JOB_CACHE_KEY % j2.job_id,
                      {'retries': refresh_jobs._JOB_MAX_RETRIES})

    self.testapp.get('/cron/refresh-jobs')

    self.ExecuteDeferredTasks('default')

    self.assertFalse(j1._Schedule.called)
    self.assertFalse(j1.Fail.called)

    self.assertFalse(j2._Schedule.called)
    self.assertTrue(j2.Fail.called)

  def testGet_OverRetryLimit(self):
    j1 = job_module.Job.New((), ())
    j1.task = '123'
    j1.started = True
    j1.put()
    j1._Schedule = mock.MagicMock()
    j1.Fail = mock.MagicMock()

    j2 = job_module.Job.New((), ())
    j2.task = '123'
    j2.started = True
    j2.updated = datetime.datetime.utcnow() - datetime.timedelta(hours=8)
    j2.put()
    j2._Schedule = mock.MagicMock()  # pylint: disable=invalid-name
    j2.Fail = mock.MagicMock()  # pylint: disable=invalid-name

    layered_cache.Set(refresh_jobs._JOB_CACHE_KEY % j2.job_id,
                      {'retries': refresh_jobs._JOB_MAX_RETRIES + 1})

    self.testapp.get('/cron/refresh-jobs')

    self.ExecuteDeferredTasks('default')

    self.assertFalse(j1._Schedule.called)
    self.assertFalse(j1.Fail.called)

    self.assertFalse(j2._Schedule.called)
    self.assertFalse(j2.Fail.called)
