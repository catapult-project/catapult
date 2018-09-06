# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

from google.appengine.ext import ndb

from dashboard import short_uri
from dashboard.common import testing_common
from dashboard.models import graph_data
from dashboard.models import page_state


class ShortUriTest(testing_common.TestCase):

  def setUp(self):
    super(ShortUriTest, self).setUp()
    self.SetUpApp([('/short_uri', short_uri.ShortUriHandler)])

  def testUpgradeOld(self):
    t = graph_data.TestMetadata(
        has_rows=True, id='master/bot/suite/measurement/case')
    t.UpdateSheriff()
    t.put()
    page_state.PageState(id='test_sid', value=json.dumps({
        'charts': [
            [
                ['master/bot/suite/measurement', ['all']],
            ],
        ]})).put()
    response = self.testapp.get('/short_uri', {'sid': 'test_sid', 'v2': 'true'})
    expected = {
        'testSuites': ['suite'],
        'measurements': ['measurement'],
        'bots': ['master:bot'],
        'testCases': ['case'],
    }
    actual = json.loads(response.body)['chartSections'][0]['parameters']
    self.assertEqual(expected, actual)
    self.assertEqual(response.body,
                     ndb.Key('PageState', 'test_sid').get().value_v2)

  def testUpgradeNew(self):
    t = graph_data.TestMetadata(
        has_rows=True, id='master/bot/suite/measurement/case')
    t.UpdateSheriff()
    t.put()
    page_state.PageState(id='test_sid', value=json.dumps({
        'charts': [
            {
                'seriesGroups': [
                    ['master/bot/suite/measurement', ['measurement']],
                ],
            },
        ],
    })).put()
    response = self.testapp.get('/short_uri', {'sid': 'test_sid', 'v2': 'true'})
    expected = {
        'testSuites': ['suite'],
        'measurements': ['measurement'],
        'bots': ['master:bot'],
        'testCases': [],
    }
    actual = json.loads(response.body)['chartSections'][0]['parameters']
    self.assertEqual(expected, actual)
    self.assertEqual(response.body,
                     ndb.Key('PageState', 'test_sid').get().value_v2)

  def testPostAndGet(self):
    sample_page_state = {
        'charts': [['Chromium/win/sunspider/total', 'important']]
    }

    response = self.testapp.post(
        '/short_uri', {'page_state': json.dumps(sample_page_state)})
    page_state_id = json.loads(response.body)['sid']
    self.assertIsNotNone(page_state_id)

    response = self.testapp.get('/short_uri', {'sid': page_state_id})
    self.assertEqual(sample_page_state, json.loads(response.body))

  def testGet_InvalidSID(self):
    self.testapp.get('/short_uri', {'sid': '123xyz'}, status=400)

  def testGet_NoSID(self):
    self.testapp.get('/short_uri', status=400)

  def testPost_NoPageState(self):
    self.testapp.post('/short_uri', status=400)


if __name__ == '__main__':
  unittest.main()
