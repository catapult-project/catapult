# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for update_test_metadata module."""

import base64
import json
import unittest

import mock
import webapp2
import webtest

from dashboard import testing_common
from dashboard import units_to_direction
from dashboard import update_test_metadata
from dashboard.models import anomaly
from dashboard.models import graph_data

_MOCK_TESTS = [
    ['Chromium'],
    ['win7', 'mac'],
    {
        'SuiteA': {'sub_a': {'trace_a': {}, 'trace_b': {}}},
        'SuiteB': {'sub_b': {'trace_1': {}, 'trace_b': {}}},
    }
]

_UNIT_JSON = json.dumps({
    'description': 'foo',
    'ms': {'improvement_direction': 'down'},
    'score': {'improvement_direction': 'up'},
})


def _MockFetch(url):
  if update_test_metadata._UNIT_JSON_PATH in url:
    return testing_common.FakeResponseObject(
        200, base64.encodestring(_UNIT_JSON))


class UpdateTestMetadataTest(testing_common.TestCase):

  def setUp(self):
    super(UpdateTestMetadataTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/update_test_metadata',
        update_test_metadata.UpdateTestMetadataHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(side_effect=_MockFetch))
  def testGet_UpdatesImprovementDirection(self):
    testing_common.AddDataToMockDataStore(*_MOCK_TESTS)
    self.testapp.get('/update_test_metadata')
    tests = graph_data.Test.query().fetch()
    self.assertEqual(16, len(tests))

    self.assertEqual(
        anomaly.DOWN,
        units_to_direction.GetImprovementDirectionForUnit('ms'))
    self.assertEqual(
        anomaly.UP,
        units_to_direction.GetImprovementDirectionForUnit('score'))
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirectionForUnit('does-not-exist'))


if __name__ == '__main__':
  unittest.main()
