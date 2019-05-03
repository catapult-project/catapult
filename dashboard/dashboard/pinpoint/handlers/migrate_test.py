# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

import mock

from dashboard.pinpoint.handlers import migrate
from dashboard.pinpoint.models import job
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint import test


class MigrateTest(test.TestCase):

  def setUp(self):
    super(MigrateTest, self).setUp()

    patcher = mock.patch.object(migrate, 'datetime', _DatetimeStub())
    self.addCleanup(patcher.stop)
    patcher.start()

    for _ in xrange(20):
      job.Job.New((), ())

  def testGet_NoMigration(self):
    response = self.testapp.get('/api/migrate', status=200)
    self.assertEqual(response.normal_body, '{}')

  def testGet_MigrationInProgress(self):
    expected = {
        'count': 0,
        'started': 'Date Time',
        'total': 20,
    }

    response = self.testapp.post('/api/migrate', status=200)
    self.assertEqual(response.normal_body, json.dumps(expected))

    response = self.testapp.get('/api/migrate', status=200)
    self.assertEqual(response.normal_body, json.dumps(expected))

  def testPost_EndToEnd(self):
    expected = {
        'count': 0,
        'started': 'Date Time',
        'total': 20,
    }

    job_state.JobState.__setstate__ = _JobStateSetState

    response = self.testapp.post('/api/migrate', status=200)
    self.assertEqual(response.normal_body, json.dumps(expected))

    expected = {
        'count': 10,
        'started': 'Date Time',
        'total': 20,
    }

    task_responses = self.ExecuteTaskQueueTasks(
        '/api/migrate', 'default', recurse=False)
    self.assertEqual(task_responses[0].normal_body, json.dumps(expected))

    task_responses = self.ExecuteTaskQueueTasks(
        '/api/migrate', 'default', recurse=False)
    self.assertEqual(task_responses[0].normal_body, '{}')

    del job_state.JobState.__setstate__

    jobs = job.Job.query().fetch()
    for j in jobs:
      self.assertEqual(j.state._new_field, 'new value')


def _JobStateSetState(self, state):
  self.__dict__ = state
  self._new_field = 'new value'


class _DatetimeStub(object):

  # pylint: disable=invalid-name
  class datetime(object):

    def isoformat(self):
      return 'Date Time'

    @classmethod
    def now(cls):
      return cls()
