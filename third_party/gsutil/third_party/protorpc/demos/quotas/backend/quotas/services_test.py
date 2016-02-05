#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""QuotaService tests."""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import unittest
import time

from protorpc import test_util

from quotas import services

SIMPLE_CONFIG = services.QuotaConfig(
  buckets=[
    services.QuotaConfig.Bucket(
      name='DISK',
      initial_tokens=1000),
    services.QuotaConfig.Bucket(
      name='EMAILS',
      initial_tokens=10,
      refresh_every=10)
    ])


class QuotaTestBase(test_util.TestCase):

  def MakeState(self, disk=None, emails=None, next_refresh=2000, state=None):
    state = state or {}
    if disk:
      state['DISK'] = disk, None
    if emails:
      state['EMAILS'] = emails, next_refresh
    buckets = dict((bucket.name, bucket) for bucket in SIMPLE_CONFIG.buckets)
    return services.QuotaState(state, buckets)

  def setUp(self):
    self.current_time = 1000.5
    self.original_time = time.time
    time.time = self.Time

  def tearDown(self):
    time.time = self.original_time

  def Time(self):
    return self.current_time


class QuotaStateTest(QuotaTestBase):

  def setUp(self):
    super(QuotaStateTest, self).setUp()
    self.state = self.MakeState()

  def testGetRemainingTokens(self):
    self.state.begin_transaction()
    self.assertEquals(1000, self.state.get_remaining_tokens('DISK'))
    self.assertEquals(10, self.state.get_remaining_tokens('EMAILS'))
    self.assertEquals(None, self.state.get_remaining_tokens('UNKNOWN'))
    self.state.abort_transaction()

    self.state = self.MakeState(200, 5)
    self.state.begin_transaction()
    self.assertEquals(200, self.state.get_remaining_tokens('DISK'))
    self.assertEquals(5, self.state.get_remaining_tokens('EMAILS'))
    self.assertEquals(None, self.state.get_remaining_tokens('UNKNOWN'))
    self.state.abort_transaction()

  def testCheckQuota(self):
    self.state.begin_transaction()
    self.assertEquals(100, self.state.check_quota('DISK', 100))
    self.assertEquals(1000, self.state.check_quota('DISK', 1000))
    self.assertEquals(1000, self.state.check_quota('DISK', 1001))
    self.assertEquals(-1001, self.state.check_quota('DISK', -1001))
    self.assertEquals(1, self.state.check_quota('EMAILS', 1))
    self.assertEquals(10, self.state.check_quota('EMAILS', 10))
    self.assertEquals(10, self.state.check_quota('EMAILS', 11))
    self.assertEquals(-11, self.state.check_quota('EMAILS', -11))
    self.assertEquals(None, self.state.check_quota('UNKNOWN', 10))
    self.state.abort_transaction()

  def testDeduct(self):
    self.state.begin_transaction()
    self.assertEquals(100, self.state.deduct_quota('DISK', 100))
    self.assertEquals(900, self.state.get_remaining_tokens('DISK'))
    self.state.commit_transaction()

    self.state.begin_transaction()
    self.assertEquals(900, self.state.deduct_quota('DISK', 900))
    self.assertEquals(0, self.state.get_remaining_tokens('DISK'))
    self.state.commit_transaction()

    self.state.begin_transaction()
    self.assertEquals(0, self.state.deduct_quota('DISK', 1))
    self.assertEquals(0, self.state.get_remaining_tokens('DISK'))
    self.state.commit_transaction()

    self.state.begin_transaction()
    self.assertEquals(10, self.state.deduct_quota('EMAILS', 11))
    self.assertEquals(0, self.state.get_remaining_tokens('EMAILS'))
    self.state.commit_transaction()

    self.state.begin_transaction()
    self.assertEquals(0, self.state.deduct_quota('DISK', 1))
    self.assertEquals(0, self.state.get_remaining_tokens('EMAILS'))
    self.state.commit_transaction()

  def testDeductAbort(self):
    self.state.begin_transaction()
    self.assertEquals(100, self.state.deduct_quota('DISK', 100))
    self.assertEquals(900, self.state.get_remaining_tokens('DISK'))
    self.state.abort_transaction()

    self.state.begin_transaction()
    self.assertEquals(1000, self.state.get_remaining_tokens('DISK'))
    self.state.abort_transaction()

  def testAutoRefresh(self):
    # Use some quota.
    self.state.begin_transaction()
    self.state.deduct_quota('DISK', 100)
    self.state.deduct_quota('EMAILS', 10)
    self.state.commit_transaction()

    # Cause refresh.
    self.current_time += 20

    # Emails should now be restored.
    self.state.begin_transaction()
    self.assertEquals(900, self.state.get_remaining_tokens('DISK'))
    self.assertEquals(10, self.state.get_remaining_tokens('EMAILS'))
    self.state.commit_transaction()

  def testAutoRefreshDuringTransaction(self):
    # Use some quota quota.
    self.state.begin_transaction()
    self.state.deduct_quota('DISK', 100)
    self.state.deduct_quota('EMAILS', 10)

    # Refresh is too late for transaction.
    self.current_time += 20

    self.assertEquals(900, self.state.get_remaining_tokens('DISK'))
    self.assertEquals(0, self.state.get_remaining_tokens('EMAILS'))
    self.state.commit_transaction()

  def testDeductSameBucket(self):
    self.state.begin_transaction()
    self.state.deduct_quota('DISK', 100)
    self.assertRaises(AssertionError,
                      self.state.deduct_quota, 'DISK', 100)
    self.state.commit_transaction()


class QuotaServiceTest(QuotaTestBase):

  def setUp(self):
    super(QuotaServiceTest, self).setUp()
    self.states = {}
    self.service = services.QuotaService(SIMPLE_CONFIG, {})

  def MakeCheckQuotaRequest(self, user, quotas):
    return services.QuotaRequest(
      user=user,
      quotas=[
        services.QuotaCheck(name=bucket,
                            tokens=tokens,
                            mode=services.QuotaCheck.Mode(mode))
        for bucket, tokens, mode in quotas
      ])

  def AssertRemaining(self, user, remaining_quotas):
    response = self.service.get_quota_state(
      services.QuotaStateRequest(user=user))
    self.assertEquals(len(remaining_quotas), len(response.bucket_states))
    for (name, remaining), bucket_state in zip(remaining_quotas,
                                               response.bucket_states):
      self.assertEquals(name, bucket_state.name)
      self.assertEquals(remaining, bucket_state.remaining_tokens)

  def testCheckQuotaAll(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 100, 'ALL'),
                                          ('EMAILS', 10, 'ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.OK, response.all_status)
    self.assertFalse(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[0].status)
    self.assertEquals(100, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[1].status)
    self.assertEquals(10, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 900), ('EMAILS', 0)])

  def testCheckQuotaAll_SomeAvailable(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 100, 'ALL'),
                                          ('EMAILS', 11, 'ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.SOME, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[0].status)
    self.assertEquals(100, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.SOME, response.results[1].status)
    self.assertEquals(10, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 1000), ('EMAILS', 10)])

  def testCheckQuotaAll_NoneAvailable(self):
    # Deplete all quota.
    self.service.check_quota(self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1000, 'ALL'),
                                          ('EMAILS', 10, 'ALL'),
                                         ]))

    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1, 'ALL'),
                                          ('EMAILS', 1, 'ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.NONE, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[0].status)
    self.assertEquals(0, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[1].status)
    self.assertEquals(0, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 0), ('EMAILS', 0)])

  def testCheckQuotaAll_SomeAndNone(self):
    # Deplete some quota.
    self.service.check_quota(self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1000, 'ALL'),
                                         ]))

    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1, 'ALL'),
                                          ('EMAILS', 11, 'ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.SOME, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[0].status)
    self.assertEquals(0, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.SOME, response.results[1].status)
    self.assertEquals(10, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 0), ('EMAILS', 10)])

  def testCheckQuotaSome(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 500, 'ALL'),
                                          ('EMAILS', 5, 'SOME'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.OK, response.all_status)
    self.assertFalse(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[0].status)
    self.assertEquals(500, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[1].status)
    self.assertEquals(5, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 500), ('EMAILS', 5)])

  def testCheckQuotaSome_SomeAvailable(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 100, 'SOME'),
                                          ('EMAILS', 11, 'SOME'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.SOME, response.all_status)
    self.assertFalse(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[0].status)
    self.assertEquals(100, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.SOME, response.results[1].status)
    self.assertEquals(10, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 900), ('EMAILS', 0)])

  def testCheckQuotaSome_NoneAvailable(self):
    # Deplete all quota.
    self.service.check_quota(self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1000, 'ALL'),
                                          ('EMAILS', 10, 'ALL'),
                                         ]))

    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1, 'SOME'),
                                          ('EMAILS', 1, 'SOME'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.NONE, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[0].status)
    self.assertEquals(0, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[1].status)
    self.assertEquals(0, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 0), ('EMAILS', 0)])

  def testCheckQuotaSome_SomeAndNone(self):
    # Deplete some quota.
    self.service.check_quota(self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1000, 'ALL'),
                                         ]))

    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1, 'SOME'),
                                          ('EMAILS', 11, 'SOME'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.SOME, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(2, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[0].status)
    self.assertEquals(0, response.results[0].available)

    self.assertEquals(
      services.CheckResult.Status.SOME, response.results[1].status)
    self.assertEquals(10, response.results[1].available)

    self.AssertRemaining('bob', [('DISK', 0), ('EMAILS', 10)])

  def testCheckQuotaCheckAll(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 500, 'CHECK_ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.OK, response.all_status)
    self.assertFalse(response.denied)
    self.assertEquals(1, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.OK, response.results[0].status)
    self.assertEquals(500, response.results[0].available)

    self.AssertRemaining('bob', [('DISK', 1000), ('EMAILS', 10)])

  def testCheckQuotaCheckAll_SomeAvailable(self):
    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1001, 'CHECK_ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.SOME, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(1, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.SOME, response.results[0].status)
    self.assertEquals(1000, response.results[0].available)

    self.AssertRemaining('bob', [('DISK', 1000), ('EMAILS', 10)])

  def testCheckQuotaCheckAll_NoneAvailable(self):
    # Deplete all quota.
    self.service.check_quota(self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1000, 'ALL'),
                                         ]))

    request = self.MakeCheckQuotaRequest('bob',
                                         [('DISK', 1, 'CHECK_ALL'),
                                         ])
    response = self.service.check_quota(request)

    self.assertEquals(services.CheckResult.Status.NONE, response.all_status)
    self.assertTrue(response.denied)
    self.assertEquals(1, len(response.results))

    self.assertEquals(
      services.CheckResult.Status.NONE, response.results[0].status)
    self.assertEquals(0, response.results[0].available)

    self.AssertRemaining('bob', [('DISK', 0), ('EMAILS', 10)])


if __name__ == '__main__':
  unittest.main()
