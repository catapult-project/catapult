# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for file_bug module."""

import json
import unittest

import mock
import webapp2
import webtest

from google.appengine.ext import ndb

# Importing mock_oauth2_decorator before file_bug mocks out
# OAuth2Decorator usage in that file.
# pylint: disable=unused-import
from dashboard import mock_oauth2_decorator
# pylint: enable=unused-import

from dashboard import file_bug
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import sheriff
from dashboard.models import try_job


class FileBugTest(testing_common.TestCase):

  def setUp(self):
    super(FileBugTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/file_bug', file_bug.FileBugHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@google.com', is_admin=True)

  def tearDown(self):
    super(FileBugTest, self).tearDown()
    mock_oauth2_decorator.MockOAuth2Decorator.past_bodies = []

  def _AddAlertsToDataStore(self, first_fake_rev=10000):
    """Adds sample data and returns a dict of rev to anomaly key."""
    # Add sample sheriff, masters, bots, and tests.
    sheriff_key = sheriff.Sheriff(
        id='Chromium Perf Sheriff', email='sullivan@google.com').put()
    testing_common.AddDataToMockDataStore(['ChromiumGPU'], ['linux-release'], {
        'scrolling-benchmark': {
            'first_paint': {},
            'mean_frame_time': {},
        }
    })

    # Get the keys of the two tests that were added.
    test_keys = map(utils.TestKey, [
        'ChromiumGPU/linux-release/scrolling-benchmark/first_paint',
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time',
    ])

    key_map = {}

    # Add Anomaly entities to the two tests alternately.
    for end_rev in range(first_fake_rev, first_fake_rev + 20, 10):
      test_key = test_keys[0] if end_rev % 20 == 0 else test_keys[1]
      anomaly_key = anomaly.Anomaly(
          start_revision=(end_rev - 5), end_revision=end_rev, test=test_key,
          median_before_anomaly=100, median_after_anomaly=200,
          sheriff=sheriff_key).put()
      key_map[end_rev] = anomaly_key.urlsafe()

    return key_map

  def testGet_WithNoKeys_ShowsError(self):
    # When a request is made and no keys parameter is given,
    # an error message is shown in the reply.
    response = self.testapp.get(
        '/file_bug?summary=s&description=d&finish=true')
    self.assertIn('<div class="error">', response.body)
    self.assertIn('No alerts specified', response.body)

  def testGet_WithNoFinish_ShowsForm(self):
    # When a GET request is sent with keys specified but the finish parameter
    # is not given, the response should contain a form for the sheriff to fill
    # in bug details (summary, description, etc).
    key_map = self._AddAlertsToDataStore()
    response = self.testapp.get(
        '/file_bug?summary=s&description=d&keys=%s' % key_map[10000])
    self.assertEqual(1, len(response.html('form')))

  def testInternalBugLabel(self):
    # If any of the alerts are marked as internal-only, which should happen
    # when the corresponding test is internal-only, then the create bug dialog
    # should suggest adding a Restrict-View-Google label.
    key_map = self._AddAlertsToDataStore()
    anomaly_entity = ndb.Key(urlsafe=key_map[10000]).get()
    anomaly_entity.internal_only = True
    anomaly_entity.put()
    response = self.testapp.get(
        '/file_bug?summary=s&description=d&keys=%s' % key_map[10000])
    self.assertIn('Restrict-View-Google', response.body)

  @mock.patch(
      'google.appengine.api.app_identity.get_default_version_hostname',
      mock.MagicMock(return_value='chromeperf.appspot.com'))
  def _PostSampleBug(self, fake_rev=10000):
    key_map = self._AddAlertsToDataStore(fake_rev)
    response = self.testapp.post(
        '/file_bug',
        [
            ('keys', '%s,%s' % (key_map[fake_rev], key_map[fake_rev + 10])),
            ('summary', 's'),
            ('description', 'd\n'),
            ('finish', 'true'),
            ('label', 'one'),
            ('label', 'two'),
        ])
    return response

  @mock.patch.object(
      file_bug, '_GetAllCurrentVersionsFromOmahaProxy',
      mock.MagicMock(return_value=[]))
  def testGet_WithFinish_CreatesBug(self):
    # When a POST request is sent with keys specified and with the finish
    # parameter given, an issue will be created using the issue tracker
    # API, and the anomalies will be updated, and a response page will
    # be sent which indicates success.
    mock_oauth2_decorator.HTTP_MOCK.data = '{"id": 277761}'
    response = self._PostSampleBug()

    # The response page should have a bug number.
    self.assertIn('277761', response.body)

    # The anomaly entities should be updated.
    for anomaly_entity in anomaly.Anomaly.query().fetch():
      if anomaly_entity.end_revision in [10000, 10010]:
        self.assertEqual(277761, anomaly_entity.bug_id)
      else:
        self.assertIsNone(anomaly_entity.bug_id)

    # Two HTTP requests are made when filing a bug; only test 2nd request.
    comment = json.loads(mock_oauth2_decorator.HTTP_MOCK.body)['content']
    self.assertIn('https://chromeperf.appspot.com/group_report?bug_id=277761',
                  comment)
    self.assertIn('https://chromeperf.appspot.com/group_report?keys=', comment)
    self.assertIn('\n\n\nBot(s) for this bug\'s original alert(s):\n\n'
                  'linux-release', comment)

    # A bisect job should be added.
    bisect_jobs = try_job.TryJob.query().fetch()
    self.assertEqual(1, len(bisect_jobs))

  @mock.patch.object(
      file_bug, '_GetAllCurrentVersionsFromOmahaProxy',
      mock.MagicMock(return_value=[
          {
              'versions': [
                  {'branch_base_position': '10000', 'current_version': '2.0'},
                  {'branch_base_position': '9990', 'current_version': '1.0'}
              ]
          }
      ]))
  def testGet_WithFinish_LabelsBugWithMilestone(self):
    # Here, we expect the bug to have the following start revisions: [9995,
    # 10005] and the milestones are M-1 for rev 9990 and M-2 for 10000. Hence
    # the expected behavior is to label the bug M-2 since 9995 (lowest possible
    # revision introducing regression) is less than 10000 (revision for M-2).
    self._PostSampleBug()
    self.assertIn(u'M-2', json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(return_value=testing_common.FakeResponseObject(
          200, json.dumps([
              {
                  'versions': [
                      {'branch_base_position': '9999',
                       'current_version': '3.0.1234.32'},
                      {'branch_base_position': '10000',
                       'current_version': '2.0'},
                      {'branch_base_position': '9990',
                       'current_version': '1.0'}
                  ]
              }
          ]))))
  def testGet_WithFinish_LabelsBugWithLowestMilestonePossible(self):
    # Here, we expect the bug to have the following start revisions: [9995,
    # 10005] and the milestones are M-1 for rev 9990, M-2 for 10000 and M-3 for
    # 9999. Hence the expected behavior is to label the bug M-2 since 9995
    # is less than 10000 (M-2) and 9999 (M-3) AND M-2 is lower than M-3.
    self._PostSampleBug()
    self.assertIn(u'M-2', json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(return_value=testing_common.FakeResponseObject(
          200, '[]')))
  def testGet_WithFinish_SucceedsWithNoVersions(self):
    # Here, we test that we don't label the bug with an unexpected value when
    # there is no version information from omahaproxy (for whatever reason)
    self._PostSampleBug()
    labels = json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels']
    self.assertEqual(0, len([x for x in labels if x.startswith(u'M-')]))

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(return_value=testing_common.FakeResponseObject(
          200, json.dumps([
              {
                  'versions': [
                      {'branch_base_position': '0', 'current_version': '1.0'}
                  ]
              }
          ]))))
  def testGet_WithFinish_SucceedsWithRevisionOutOfRange(self):
    # Here, we test that we label the bug with the highest milestone when the
    # revision introducing regression is beyond all milestones in the list.
    self._PostSampleBug()
    self.assertIn(u'M-1', json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(return_value=testing_common.FakeResponseObject(
          200, json.dumps([
              {
                  'versions': [
                      {'branch_base_position': 'N/A', 'current_version': 'N/A'}
                  ]
              }
          ]))))
  @mock.patch('logging.warn')
  def testGet_WithFinish_SucceedsWithNAAndLogsWarning(self, mock_warn):
    self._PostSampleBug()
    labels = json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels']
    self.assertEqual(0, len([x for x in labels if x.startswith(u'M-')]))
    self.assertEqual(1, mock_warn.call_count)


if __name__ == '__main__':
  unittest.main()
