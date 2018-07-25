# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import unittest

from dashboard.api import api_auth
from dashboard.api import report_generate
from dashboard.common import testing_common
from dashboard.models import report_template


@report_template.Static(
    internal_only=False,
    template_id='test-external',
    name='Test:External',
    modified=datetime.datetime.now())
def _External(unused_revisions):
  return 'external'


@report_template.Static(
    internal_only=True,
    template_id='test-internal',
    name='Test:Internal',
    modified=datetime.datetime.now())
def _Internal(unused_revisions):
  return 'internal'


class ReportGenerateTest(testing_common.TestCase):

  def setUp(self):
    super(ReportGenerateTest, self).setUp()
    self.SetUpApp([
        ('/api/report/generate', report_generate.ReportGenerateHandler),
    ])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])

  def _Post(self, **params):
    return json.loads(self.Post('/api/report/generate', params).body)

  def testInvalid(self):
    self.Post('/api/report/generate', dict(), status=400)
    self.Post('/api/report/generate', dict(revisions='a'), status=400)
    self.Post('/api/report/generate', dict(revisions='0'), status=400)
    self.Post('/api/report/generate', dict(revisions='0', id='x'), status=404)

  def testInternal_GetReport(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = self._Post(revisions='latest', id='test-internal')
    self.assertEqual('internal', response['report'])
    self.assertEqual('test-internal', response['id'])
    self.assertEqual('Test:Internal', response['name'])
    self.assertEqual(True, response['internal'])

  def testAnonymous_GetReport(self):
    self.SetCurrentUserOAuth(None)
    self.Post('/api/report/generate', dict(
        revisions='latest', id='test-internal'), status=404)
    response = self._Post(revisions='latest', id='test-external')
    self.assertEqual('external', response['report'])
    self.assertEqual('test-external', response['id'])
    self.assertEqual('Test:External', response['name'])
    self.assertEqual(False, response['internal'])


if __name__ == '__main__':
  unittest.main()
