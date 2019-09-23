# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

import mock

from dashboard.api import api_auth
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.pinpoint.handlers import migrate
from dashboard.pinpoint.models import job
from dashboard.pinpoint.models import job_state
from dashboard.pinpoint import test


class MigrateAuthTest(test.TestCase):
  def setUp(self):
    super(MigrateAuthTest, self).setUp()

    patcher = mock.patch.object(migrate, 'datetime', _DatetimeStub())
    self.addCleanup(patcher.stop)
    patcher.start()

    for _ in range(20):
      job.Job.New((), ())

  def _SetupCredentials(self, user, client_id, is_internal, is_admin):
    email = user.email()
    testing_common.SetIsInternalUser(email, is_internal)
    testing_common.SetIsAdministrator(email, is_admin)
    self.SetCurrentUserOAuth(user)
    self.SetCurrentClientIdOAuth(client_id)
    self.SetCurrentUser(email)

  def testGet_ExternalUser_Fails(self):
    self._SetupCredentials(testing_common.EXTERNAL_USER, None, False, False)

    self.testapp.get('/api/migrate', status=403)

  def testGet_InternalUser_NotAdmin_Fails(self):
    self._SetupCredentials(
        testing_common.INTERNAL_USER, api_auth.OAUTH_CLIENT_ID_WHITELIST[0],
        True, False)

    self.testapp.get('/api/migrate', status=403)


class MigrateTest(MigrateAuthTest):
  def setUp(self):
    super(MigrateTest, self).setUp()

    print('MigrateTest')
    self._SetupCredentials(
        testing_common.INTERNAL_USER, api_auth.OAUTH_CLIENT_ID_WHITELIST[0],
        True, True)

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

    self.ExecuteDeferredTasks('default', recurse=False)
    status = stored_object.Get(migrate._STATUS_KEY)
    self.assertEqual(status, expected)

    self.ExecuteDeferredTasks('default', recurse=False)
    status = stored_object.Get(migrate._STATUS_KEY)
    self.assertEqual(status, None)

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
