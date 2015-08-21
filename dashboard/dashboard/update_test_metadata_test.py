# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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


_UNIT_JSON = json.dumps({
    'description': 'foo',
    'ms': {'improvement_direction': 'down'},
    'score': {'improvement_direction': 'up'},
})


def _MakeMockFetch(base64_encoded=True, malformed_json=False, status=200):
  """Returns a mock fetch object that returns a canned response."""
  def _MockFetch(unused_url):  # pylint: disable=unused-argument
    response_text = _UNIT_JSON
    if malformed_json:
      response_text = 'this is not json'
    if base64_encoded:
      response_text = base64.b64encode(response_text)
    return testing_common.FakeResponseObject(status, response_text)
  return mock.MagicMock(side_effect=_MockFetch)


class UpdateTestMetadataTest(testing_common.TestCase):

  def setUp(self):
    super(UpdateTestMetadataTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/update_test_metadata',
          update_test_metadata.UpdateTestMetadataHandler)])
    self.testapp = webtest.TestApp(app)

  @mock.patch('google.appengine.api.urlfetch.fetch', _MakeMockFetch())
  def testGet_UpdatesImprovementDirection(self):
    self.testapp.get('/update_test_metadata')
    self.assertEqual(
        anomaly.DOWN,
        units_to_direction.GetImprovementDirection('ms'))
    self.assertEqual(
        anomaly.UP,
        units_to_direction.GetImprovementDirection('score'))
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirection('does-not-exist'))

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(malformed_json=True))
  @mock.patch('logging.error')
  def testGet_MalformedJson_ReportsError(self, mock_logging_error):
    self.testapp.get('/update_test_metadata', status=500)
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirection('ms'))
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirection('score'))
    self.assertEqual(2, mock_logging_error.call_count)

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(status=500))
  @mock.patch('logging.error')
  def testGet_ErrorFetching_ReportsError(self, mock_logging_error):
    self.testapp.get('/update_test_metadata', status=500)
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirection('ms'))
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirection('score'))
    self.assertEqual(2, mock_logging_error.call_count)

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(base64_encoded=False))
  @mock.patch('logging.error')
  def testDownloadChromiumFile_BadEncoding(self, mock_logging_error):
    self.assertIsNone(
        update_test_metadata.DownloadChromiumFile('foo.json'))
    self.assertEqual(1, mock_logging_error.call_count)

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(status=400))
  @mock.patch('logging.error')
  def testDownloadChromiumFile_Non200Status(self, mock_logging_error):
    self.assertIsNone(
        update_test_metadata.DownloadChromiumFile('foo.json'))
    self.assertEqual(1, mock_logging_error.call_count)


if __name__ == '__main__':
  unittest.main()
