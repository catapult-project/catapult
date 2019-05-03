# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import mock

from dashboard.common import layered_cache
from dashboard.pinpoint.handlers import refresh_jobs
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint import test


class RefreshJobsTest(test.TestCase):

  def setUp(self):
    super(RefreshJobsTest, self).setUp()

  def testGet(self):
    j1 = job_module.Job.New((), ())
    j1.task = '123'
    j1.put()
    j1._Schedule = mock.MagicMock() # pylint: disable=invalid-name
    j1.Fail = mock.MagicMock() # pylint: disable=invalid-name

    j2 = job_module.Job.New((), ())
    j2.task = '123'
    j2.put()
    j2.updated = datetime.datetime.now() - datetime.timedelta(hours=8)
    j2.put()
    j2._Schedule = mock.MagicMock() # pylint: disable=invalid-name
    j2.Fail = mock.MagicMock() # pylint: disable=invalid-name

    self.testapp.get('/cron/refresh-jobs')

    self.ExecuteDeferredTasks('default')

    self.assertFalse(j1._Schedule.called)
    self.assertFalse(j1.Fail.called)

    self.assertTrue(j2._Schedule.called)
    self.assertFalse(j2.Fail.called)

  def testGet_RetryLimit(self):
    j1 = job_module.Job.New((), ())
    j1.task = '123'
    j1.put()
    j1._Schedule = mock.MagicMock()
    j1.Fail = mock.MagicMock()

    j2 = job_module.Job.New((), ())
    j2.task = '123'
    j2.put()
    j2.updated = datetime.datetime.now() - datetime.timedelta(hours=8)
    j2.put()
    j2._Schedule = mock.MagicMock() # pylint: disable=invalid-name
    j2.Fail = mock.MagicMock() # pylint: disable=invalid-name

    layered_cache.Set(
        refresh_jobs._JOB_CACHE_KEY % j2.job_id,
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
    j1.put()
    j1._Schedule = mock.MagicMock()
    j1.Fail = mock.MagicMock()

    j2 = job_module.Job.New((), ())
    j2.task = '123'
    j2.put()
    j2.updated = datetime.datetime.now() - datetime.timedelta(hours=8)
    j2.put()
    j2._Schedule = mock.MagicMock() # pylint: disable=invalid-name
    j2.Fail = mock.MagicMock() # pylint: disable=invalid-name

    layered_cache.Set(
        refresh_jobs._JOB_CACHE_KEY % j2.job_id,
        {'retries': refresh_jobs._JOB_MAX_RETRIES+1})

    self.testapp.get('/cron/refresh-jobs')

    self.ExecuteDeferredTasks('default')

    self.assertFalse(j1._Schedule.called)
    self.assertFalse(j1.Fail.called)

    self.assertFalse(j2._Schedule.called)
    self.assertFalse(j2.Fail.called)
