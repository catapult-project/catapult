# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
import webapp2
import webtest

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


class FileBugTest(testing_common.TestCase):

  def setUp(self):
    super(FileBugTest, self).setUp()
    app = webapp2.WSGIApplication([('/file_bug', file_bug.FileBugHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetSheriffDomains(['chromium.org', 'google.com'])
    testing_common.SetInternalDomain('google.com')
    self.SetCurrentUser('foo@chromium.org')
    # When requests are made to the issue tracker service (using the mock
    # HTTP object in mock_oauth2_decorator), some data is expected,
    # but not necessarily read.
    mock_oauth2_decorator.HTTP_MOCK.data = '{"id": 123}'

  def tearDown(self):
    super(FileBugTest, self).tearDown()
    mock_oauth2_decorator.MockOAuth2Decorator.past_bodies = []
    self.UnsetCurrentUser()

  def _AddSampleAlerts(self):
    """Adds sample data and returns a dict of rev to anomaly key."""
    # Add sample sheriff, masters, bots, and tests.
    sheriff_key = sheriff.Sheriff(id='Sheriff').put()
    testing_common.AddTests(['ChromiumPerf'], ['linux'], {
        'scrolling': {
            'first_paint': {},
            'mean_frame_time': {},
        }
    })
    test_key1 = utils.TestKey('ChromiumPerf/linux/scrolling/first_paint')
    test_key2 = utils.TestKey('ChromiumPerf/linux/scrolling/mean_frame_time')
    anomaly_key1 = self._AddAnomaly(111995, 112005, test_key1, sheriff_key)
    anomaly_key2 = self._AddAnomaly(112000, 112010, test_key2, sheriff_key)
    return (anomaly_key1, anomaly_key2)

  def _AddAnomaly(self, start_rev, end_rev, test_key, sheriff_key):
    return anomaly.Anomaly(
        start_revision=start_rev, end_revision=end_rev, test=test_key,
        median_before_anomaly=100, median_after_anomaly=200,
        sheriff=sheriff_key).put()

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
    alert_keys = self._AddSampleAlerts()
    response = self.testapp.get(
        '/file_bug?summary=s&description=d&keys=%s' % alert_keys[0].urlsafe())
    self.assertEqual(1, len(response.html('form')))

  def testInternalBugLabel(self):
    # If any of the alerts are marked as internal-only, which should happen
    # when the corresponding test is internal-only, then the create bug dialog
    # should suggest adding a Restrict-View-Google label.
    self.SetCurrentUser('foo@google.com')
    alert_keys = self._AddSampleAlerts()
    anomaly_entity = alert_keys[0].get()
    anomaly_entity.internal_only = True
    anomaly_entity.put()
    response = self.testapp.get(
        '/file_bug?summary=s&description=d&keys=%s' % alert_keys[0].urlsafe())
    self.assertIn('Restrict-View-Google', response.body)

  @mock.patch(
      'google.appengine.api.app_identity.get_default_version_hostname',
      mock.MagicMock(return_value='chromeperf.appspot.com'))
  @mock.patch.object(
      file_bug.auto_bisect, 'StartNewBisectForBug',
      mock.MagicMock(return_value={'issue_id': 123, 'issue_url': 'foo.com'}))
  def _PostSampleBug(self):
    alert_keys = self._AddSampleAlerts()
    response = self.testapp.post(
        '/file_bug',
        [
            ('keys', '%s,%s' % (alert_keys[0].urlsafe(),
                                alert_keys[1].urlsafe())),
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
  @mock.patch.object(
      file_bug.auto_bisect, 'StartNewBisectForBug',
      mock.MagicMock(return_value={'issue_id': 123, 'issue_url': 'foo.com'}))
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
      if anomaly_entity.end_revision in [112005, 112010]:
        self.assertEqual(277761, anomaly_entity.bug_id)
      else:
        self.assertIsNone(anomaly_entity.bug_id)

    # Two HTTP requests are made when filing a bug; only test 2nd request.
    comment = json.loads(mock_oauth2_decorator.HTTP_MOCK.body)['content']
    self.assertIn(
        'https://chromeperf.appspot.com/group_report?bug_id=277761', comment)
    self.assertIn('https://chromeperf.appspot.com/group_report?keys=', comment)
    self.assertIn(
        '\n\n\nBot(s) for this bug\'s original alert(s):\n\nlinux', comment)

  @mock.patch.object(
      file_bug, '_GetAllCurrentVersionsFromOmahaProxy',
      mock.MagicMock(return_value=[
          {
              'versions': [
                  {'branch_base_position': '112000', 'current_version': '2.0'},
                  {'branch_base_position': '111990', 'current_version': '1.0'}
              ]
          }
      ]))
  @mock.patch.object(
      file_bug.auto_bisect, 'StartNewBisectForBug',
      mock.MagicMock(return_value={'issue_id': 123, 'issue_url': 'foo.com'}))
  def testGet_WithFinish_LabelsBugWithMilestone(self):
    # Here, we expect the bug to have the following start revisions:
    # [111995, 112005] and the milestones are M-1 for rev 111990 and
    # M-2 for 11200. Hence the expected behavior is to label the bug
    # M-2 since 111995 (lowest possible revision introducing regression)
    # is less than 112000 (revision for M-2).
    self._PostSampleBug()
    self.assertIn(u'M-2', json.loads(
        mock_oauth2_decorator.MockOAuth2Decorator.past_bodies[-1])['labels'])

  @mock.patch(
      'google.appengine.api.urlfetch.fetch',
      mock.MagicMock(return_value=testing_common.FakeResponseObject(
          200, json.dumps([
              {
                  'versions': [
                      {'branch_base_position': '111999',
                       'current_version': '3.0.1234.32'},
                      {'branch_base_position': '112000',
                       'current_version': '2.0'},
                      {'branch_base_position': '111990',
                       'current_version': '1.0'}
                  ]
              }
          ]))))
  def testGet_WithFinish_LabelsBugWithLowestMilestonePossible(self):
    # Here, we expect the bug to have the following start revisions:
    # [111995, 112005] and the milestones are M-1 for rev 111990, M-2
    # for 112000 and M-3 for 111999. Hence the expected behavior is to
    # label the bug M-2 since 111995 is less than 112000 (M-2) and 111999
    # (M-3) AND M-2 is lower than M-3.
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
