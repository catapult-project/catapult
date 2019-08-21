# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests the FIFO Scheduler Handler."""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import mock
import sys
import logging

from dashboard.pinpoint import test
from dashboard.pinpoint.models import job
from dashboard.pinpoint.models import scheduler


class FifoSchedulerTest(test.TestCase):

  def setUp(self):
    # Intercept the logging messages, so that we can see them when we have test
    # output in failures.
    self.logger = logging.getLogger()
    self.logger.level = logging.DEBUG
    self.stream_handler = logging.StreamHandler(sys.stdout)
    self.logger.addHandler(self.stream_handler)
    self.addCleanup(self.logger.removeHandler, self.stream_handler)
    super(FifoSchedulerTest, self).setUp()

  def testSingleQueue(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock()  # pylint: disable=invalid-name

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')

    self.assertTrue(j.Start.called)

    # Ensure that the job is still running.
    job_id, queue_status = scheduler.PickJob('mock')
    self.assertEqual(job_id, j.job_id)
    self.assertEqual(queue_status, 'Running')

    # On the next poll, we need to ensure that an ongoing job doesn't get marked
    # completed until it really is completed.
    j.Start = mock.MagicMock()  # pylint: disable=invalid-name
    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')
    self.assertFalse(j.Start.called)
    job_id, queue_status = scheduler.PickJob('mock')
    self.assertEqual(job_id, j.job_id)
    self.assertEqual(queue_status, 'Running')

  def testJobCompletes(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock(
        side_effect=j._Complete)  # pylint: disable=invalid-name

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')

    self.assertTrue(j.Start.called)
    job_id, _ = scheduler.PickJob('mock')
    self.assertIsNone(job_id)

  def testJobFails(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock(side_effect=j.Fail)  # pylint: disable=invalid-name

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')

    self.assertTrue(j.Start.called)
    job_id, _ = scheduler.PickJob('mock')
    self.assertIsNone(job_id)

  def testMultipleQueues(self):
    jobs = []
    total_jobs = 2
    total_queues = 10
    for configuration_id in range(total_queues):
      for _ in range(total_jobs):
        j = job.Job.New(
            (), (),
            arguments={'configuration': 'queue-{}'.format(configuration_id)},
            comparison_mode='performance')
        j.Start = mock.MagicMock(
            side_effect=j._Complete)  # pylint: disable=invalid-name
        scheduler.Schedule(j)
        jobs.append(j)

    # We ensure that all jobs complete if we poll the fifo-scheduler.
    for _ in range(0, total_jobs):
      response = self.testapp.get('/cron/fifo-scheduler')
      self.assertEqual(response.status_code, 200)
      self.ExecuteDeferredTasks('default')

    # Check for each job that Job.Start() was called.
    for index, j in enumerate(jobs):
      self.assertTrue(j.Start.Called,
                      'job at index {} was not run!'.format(index))

  def testQueueStatsUpdates(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock(
        side_effect=j._Complete)  # pylint: disable=invalid-name

    # Check that we can find the queued job.
    stats = scheduler.QueueStats('mock')
    self.assertEquals(stats['queued_jobs'], 1)
    self.assertNotIn('running_jobs', stats)
    self.assertEquals(len(stats['queue_time_samples']), 0)

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)

    self.ExecuteDeferredTasks('default')

    self.assertTrue(j.Start.called)
    job_id, _ = scheduler.PickJob('mock')
    self.assertIsNone(job_id)

    # Check that point-in-time stats are zero, and that we have one sample.
    stats = scheduler.QueueStats('mock')
    self.assertNotIn('queued_jobs', stats)
    self.assertNotIn('running_jobs', stats)
    self.assertNotEquals(len(stats['queue_time_samples']), 0)
    self.assertEquals(len(stats['queue_time_samples'][0]), 2)

  def testJobStuckInRunning(self):
    self.skipTest('Not implemented yet.')

  def testJobCancellationSucceedsOnRunningJob(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock()  # pylint: disable=invalid-name

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')

    self.assertTrue(j.Start.called)

    # Ensure that the job is still running.
    job_id, queue_status = scheduler.PickJob('mock')
    self.assertEqual(job_id, j.job_id)
    self.assertEqual(queue_status, 'Running')

    # We can cancel a running job.
    self.assertTrue(scheduler.Cancel(j))

    # Ensure that the job is still running.
    job_id, queue_status = scheduler.PickJob('mock')
    self.assertNotEqual(job_id, j.job_id)
    self.assertNotEqual(queue_status, 'Running')

  def testJobCancellationSucceedsOnQueuedJob(self):
    j = job.Job.New((), (),
                    arguments={'configuration': 'mock'},
                    comparison_mode='performance')
    scheduler.Schedule(j)
    j.Start = mock.MagicMock()  # pylint: disable=invalid-name
    self.assertTrue(scheduler.Cancel(j))

    response = self.testapp.get('/cron/fifo-scheduler')
    self.assertEqual(response.status_code, 200)
    self.ExecuteDeferredTasks('default')
    self.assertFalse(j.Start.called)

  def testJobSamplesCapped(self):
    for _ in range(51):
      j = job.Job.New((), (),
                      arguments={'configuration': 'mock'},
                      comparison_mode='performance')
      scheduler.Schedule(j)
      j.Start = mock.MagicMock(
          side_effect=j._Complete)  # pylint: disable=invalid-name
      response = self.testapp.get('/cron/fifo-scheduler')
      self.assertEqual(response.status_code, 200)

    self.ExecuteDeferredTasks('default')

    stats = scheduler.QueueStats('mock')
    self.assertLessEqual(len(stats.get('queue_time_samples')), 50)
