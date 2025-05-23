# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from flask import Flask
import http
import itertools
import json
from unittest import mock
import unittest

import six
import webtest

from google.appengine.ext import ndb

from dashboard import group_report
from dashboard import short_uri
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import alert_group
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models import page_state
from dashboard.models.subscription import Subscription
from dashboard.services import perf_issue_service_client

SKIA_INTERNAL_HOST = 'https%3A%2F%2Fchrome-perf.corp.goog'
SKIA_EXTERNAL_HOST = 'https%3A%2F%2Fperf.luci.app'

flask_app = Flask(__name__)


@flask_app.route('/group_report', methods=['GET'])
def GroupReportGet():
  return group_report.GroupReportGet()


@flask_app.route('/group_report', methods=['POST'])
def GroupReportPost():
  return group_report.GroupReportPost()


@flask_app.route('/alerts_skia_by_key', methods=['GET'])
def SkiaAlertsByKeyHandlerGet():
  return group_report.SkiaGetAlertsByIntegerKey()


@flask_app.route('/alerts_skia_by_keys', methods=['POST'])
def SkiaAlertsByKeyHandlerPost():
  return group_report.SkiaPostAlertsByIntegerKeys()


@flask_app.route('/alerts_skia_by_bug_id', methods=['GET'])
def SkiaAlertsByBugIdHandlerGet():
  return group_report.SkiaGetAlertsByBugId()


@flask_app.route('/alerts_skia_by_sid', methods=['GET'])
def SkiaAlertsBySidHandlerGet():
  return group_report.SkiaGetAlertsBySid()


@flask_app.route('/alerts/skia/rev/<rev>', methods=['GET'])
def ListSkiaAlertsByRev(rev):
  return group_report.ListSkiaAlertsByRev(rev)


@flask_app.route('/alerts/skia/group_id/<group_id>', methods=['GET'])
def ListSkiaAlertsByGroupId(group_id):
  return group_report.ListSkiaAlertsByGroupId(group_id)


class GroupReportTest(testing_common.TestCase):

  def setUp(self):
    super().setUp()
    self.testapp = webtest.TestApp(flask_app)
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.SetCurrentUser('internal@chromium.org', is_admin=True)

  def _AddAnomalyEntities(self,
                          revision_ranges,
                          test_key,
                          subscriptions,
                          bug_id=None,
                          project_id=None,
                          group_id=None,
                          return_urlsafe_keys=True,
                          internal_only=False):
    """Adds a group of Anomaly entities to the datastore."""
    urlsafe_keys = []
    integer_keys = []
    keys = []
    for start_rev, end_rev in revision_ranges:
      subscription_names = [s.name for s in subscriptions]
      anomaly_key = anomaly.Anomaly(
          start_revision=start_rev,
          end_revision=end_rev,
          test=test_key,
          bug_id=bug_id,
          project_id=project_id,
          subscription_names=subscription_names,
          subscriptions=subscriptions,
          median_before_anomaly=100,
          median_after_anomaly=200,
          internal_only=internal_only).put()
      urlsafe_keys.append(six.ensure_str(anomaly_key.urlsafe()))
      keys.append(anomaly_key)
      integer_keys.append(anomaly_key.id())
    if group_id:
      alert_group.AlertGroup(
          id=group_id,
          anomalies=keys,
      ).put()
    return urlsafe_keys if return_urlsafe_keys else integer_keys

  def _AddTests(self):
    """Adds sample TestMetadata entities and returns their keys."""
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'],
        {'scrolling-benchmark': {
            'first_paint': {},
            'mean_frame_time': {},
        }})
    keys = [
        utils.TestKey(
            'ChromiumGPU/linux-release/scrolling-benchmark/first_paint'),
        utils.TestKey(
            'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time'),
    ]
    # By default, all TestMetadata entities have an improvement_direction of
    # UNKNOWN, meaning that neither direction is considered an improvement.
    # Here we set the improvement direction so that some anomalies are
    # considered improvements.
    for test_key in keys:
      test = test_key.get()
      test.improvement_direction = anomaly.DOWN
      test.put()
    return keys

  def _Subscription(self, suffix=""):
    """Adds a Sheriff entity and returns the key."""
    return Subscription(
        name='Chromium Perf Sheriff' + suffix,
        notification_email='sullivan@google.com')

  def testGet(self):
    response = self.testapp.get('/group_report')
    self.assertEqual('text/html', response.content_type)
    self.assertIn(b'Chrome Performance Dashboard', response.body)

  def testPost_WithAnomalyKeys_ShowsSelectedAndOverlapping(self):
    subscriptions = [
        self._Subscription(suffix=" 1"),
        self._Subscription(suffix=" 2"),
    ]
    test_keys = self._AddTests()
    selected_ranges = [(400, 900), (200, 700)]
    overlapping_ranges = [(300, 500), (500, 600), (600, 800)]
    non_overlapping_ranges = [(100, 200)]
    selected_keys = self._AddAnomalyEntities(selected_ranges, test_keys[0],
                                             subscriptions)
    self._AddAnomalyEntities(overlapping_ranges, test_keys[0], subscriptions)
    self._AddAnomalyEntities(non_overlapping_ranges, test_keys[0],
                             subscriptions)

    response = self.testapp.post('/group_report?keys=%s' %
                                 ','.join(selected_keys))
    alert_list = self.GetJsonValue(response, 'alert_list')

    # Confirm the first N keys are the selected keys.
    first_keys = [
        alert['key']
        for alert in itertools.islice(alert_list, len(selected_keys))
    ]
    self.assertSetEqual(set(selected_keys), set(first_keys))

    # Expect selected alerts + overlapping alerts,
    # but not the non-overlapping alert.
    self.assertEqual(5, len(alert_list))

  def testPost_WithInvalidSidParameter_ShowsError(self):
    response = self.testapp.post('/group_report?sid=foobar')
    error = self.GetJsonValue(response, 'error')
    self.assertIn('No anomalies specified', error)

  def testPost_WithValidSidParameter(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    selected_ranges = [(400, 900), (200, 700)]
    selected_keys = self._AddAnomalyEntities(selected_ranges, test_keys[0],
                                             [subscription])

    json_keys = six.ensure_binary(json.dumps(selected_keys))
    state_id = short_uri.GenerateHash(','.join(selected_keys))
    page_state.PageState(id=state_id, value=json_keys).put()

    response = self.testapp.post('/group_report?sid=%s' % state_id)
    alert_list = self.GetJsonValue(response, 'alert_list')

    # Confirm the first N keys are the selected keys.
    first_keys = [
        alert['key']
        for alert in itertools.islice(alert_list, len(selected_keys))
    ]
    self.assertSetEqual(set(selected_keys), set(first_keys))
    self.assertEqual(2, len(alert_list))

  def testPost_WithKeyOfNonExistentAlert_ShowsError(self):
    key = ndb.Key('Anomaly', 123)
    response = self.testapp.post('/group_report?keys=%s' %
                                 six.ensure_str(key.urlsafe()))
    error = self.GetJsonValue(response, 'error')
    self.assertEqual(
        'No Anomaly found for key %s.' % six.ensure_str(key.urlsafe()), error)

  def testPost_WithInvalidKeyParameter_ShowsError(self):
    response = self.testapp.post('/group_report?keys=foobar')
    error = self.GetJsonValue(response, 'error')
    self.assertIn('Invalid Anomaly key', error)

  def testPost_WithRevParameter(self):
    # If the rev parameter is given, then all alerts whose revision range
    # includes the given revision should be included.
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(190, 210), (200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription])
    response = self.testapp.post('/group_report?rev=200')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertEqual(3, len(alert_list))

  def testPost_WithInvalidRevParameter_ShowsError(self):
    response = self.testapp.post('/group_report?rev=foo')
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('Invalid rev "foo".', error)

  def testPost_WithBugIdParameter(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    bug_data.Bug.New(project='chromium', bug_id=123).put()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             project_id='test_project')
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.post(
        '/group_report?bug_id=123&project_id=test_project')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertEqual(3, len(alert_list))

  def testPost_WithProjectIdMissing(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    bug_data.Bug.New(project='chromium', bug_id=123).put()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             project_id='chromium')
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.post('/group_report?bug_id=123')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertEqual(3, len(alert_list))

  def testPost_WithInvalidBugIdParameter_ShowsError(self):
    response = self.testapp.post('/group_report?bug_id=foo')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertIsNone(alert_list)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('Invalid bug ID "chromium:foo".', error)

  @mock.patch.object(perf_issue_service_client, 'GetAnomaliesByAlertGroupID',
                     mock.MagicMock(return_value=[1, 2, 3]))
  def testPost_WithGroupIdParameter(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             group_id="123")
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.post('/group_report?group_id=123')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertEqual(3, len(alert_list))

  @mock.patch.object(perf_issue_service_client, 'GetAnomaliesByAlertGroupID',
                     mock.MagicMock(return_value=[1, 2, 3, '1-2-3']))
  def testPost_WithGroupIdParameterWithNonIntegerAnomalyId(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500), (600, 700)],
                             test_keys[0], [subscription],
                             group_id="123")
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.post('/group_report?group_id=123')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertEqual(3, len(alert_list))

  def testPost_WithInvalidGroupIdParameter(self):
    response = self.testapp.post('/group_report?group_id=foo')
    alert_list = self.GetJsonValue(response, 'alert_list')
    self.assertIsNone(alert_list)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('Invalid AlertGroup ID "foo".', error)

  # Tests for endpoints used by skia.

  # load by one key
  def testGet_WithAnomalyKeys_ShowsSelectedAndOverlapping_Skia(self):
    subscriptions = [
        self._Subscription(suffix=" 1"),
    ]
    test_keys = self._AddTests()
    selected_ranges = [(400, 900)]
    overlapping_ranges = [(300, 500), (500, 600), (600, 800)]
    non_overlapping_ranges = [(100, 200)]
    selected_key = self._AddAnomalyEntities(
        selected_ranges, test_keys[0], subscriptions, return_urlsafe_keys=False)
    self._AddAnomalyEntities(
        overlapping_ranges,
        test_keys[0],
        subscriptions,
        return_urlsafe_keys=False)
    self._AddAnomalyEntities(
        non_overlapping_ranges,
        test_keys[0],
        subscriptions,
        return_urlsafe_keys=False)

    response = self.testapp.get('/alerts_skia_by_key?key=%s&host=%s' %
                                (selected_key[0], SKIA_INTERNAL_HOST))
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')

    # Expect selected alerts + overlapping alerts,
    # but not the non-overlapping alert.
    self.assertEqual(1 + 3, len(anomaly_list))
    # Confirm the first few keys are the selected keys.
    self.assertEqual(anomaly_list[0]['id'], selected_key[0])

    expected_selected_keys = self.GetJsonValue(response, 'selected_keys')
    self.assertEqual(selected_key, [int(k) for k in expected_selected_keys])

  def testGet_WithInvalidKeyParameter_ShowsError_Skia(self):
    response = self.testapp.get(
        '/alerts_skia_by_key?key=str_id', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIn('Invalid Anomaly key', error)

  def testGet_WithNoKeyParameter_ShowsError_Skia(self):
    response = self.testapp.get('/alerts_skia_by_key', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('No key is found from the request.', error)

  # load by multiple keys
  def testPost_WithAnomalyKeys_ShowsSelectedAndOverlapping_Skia(self):
    subscriptions = [
        self._Subscription(suffix=" 1"),
    ]
    test_keys = self._AddTests()
    selected_ranges = [(400, 900), (200, 700)]
    overlapping_ranges = [(300, 500), (500, 600), (600, 800)]
    non_overlapping_ranges = [(100, 200)]
    selected_keys = self._AddAnomalyEntities(
        selected_ranges, test_keys[0], subscriptions, return_urlsafe_keys=False)
    self._AddAnomalyEntities(
        overlapping_ranges,
        test_keys[0],
        subscriptions,
        return_urlsafe_keys=False)
    self._AddAnomalyEntities(
        non_overlapping_ranges,
        test_keys[0],
        subscriptions,
        return_urlsafe_keys=False)

    keys_param = ','.join([str(k) for k in selected_keys])
    response = self.testapp.post_json('/alerts_skia_by_keys', {
        'keys': keys_param,
        'host': 'https://chrome-perf.corp.goog'
    })

    anomaly_list = self.GetJsonValue(response, 'anomaly_list')

    expected_sid = short_uri.GenerateHash(keys_param)
    self.assertEqual(expected_sid, self.GetJsonValue(response, 'sid'))

    self.assertEqual(0, len(anomaly_list))

    response2 = self.testapp.get('/alerts_skia_by_sid?sid=%s&host=%s' %
                                 (expected_sid, SKIA_INTERNAL_HOST))
    anomaly_list = self.GetJsonValue(response2, 'anomaly_list')
    self.assertEqual(2 + 3, len(anomaly_list))
    # Confirm the first few keys are the selected keys.
    self.assertSetEqual({a['id'] for a in anomaly_list[0:2]},
                        set(selected_keys))
    expected_selected_keys = self.GetJsonValue(response2, 'selected_keys')
    self.assertEqual(selected_keys, [int(k) for k in expected_selected_keys])

  def testPost_WithInvalidKeyParameter_ShowsError_Skia(self):
    response = self.testapp.post_json(
        '/alerts_skia_by_keys', {'keys': 'str_id'}, expect_errors=True)
    self.assertEqual({'error': 'Invalid Anomaly key given.'},
                     json.loads(response.body))
    self.assertEqual(http.HTTPStatus.BAD_REQUEST.value, response.status_code)

  def testPost_WithNoKeyParameter_ShowsError_Skia(self):
    response = self.testapp.post_json(
        '/alerts_skia_by_keys', {}, expect_errors=True)
    self.assertEqual({'error': 'No key is found from the request.'},
                     json.loads(response.body))
    self.assertEqual(http.HTTPStatus.BAD_REQUEST.value, response.status_code)

  # load by bug id
  def testGet_WithBugIdParameter_Skia(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    bug_data.Bug.New(project='chromium', bug_id=123).put()
    self._AddAnomalyEntities([(200, 300), (100, 200)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             return_urlsafe_keys=False)
    self._AddAnomalyEntities([(400, 500)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             return_urlsafe_keys=False,
                             internal_only=True)
    self._AddAnomalyEntities([(150, 250)],
                             test_keys[0], [subscription],
                             return_urlsafe_keys=False)
    response = self.testapp.get('/alerts_skia_by_bug_id?bug_id=123&host=%s' %
                                SKIA_INTERNAL_HOST)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(3, len(anomaly_list))
    expected_selected_keys = self.GetJsonValue(response, 'selected_keys')
    self.assertEqual(None, expected_selected_keys)

  def testGet_WithBugIdParameter_ExternalHost_Skia(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    bug_data.Bug.New(project='chromium', bug_id=123).put()
    self._AddAnomalyEntities([(200, 300), (100, 200)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             return_urlsafe_keys=False)
    self._AddAnomalyEntities([(400, 500)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             return_urlsafe_keys=False,
                             internal_only=True)
    self._AddAnomalyEntities([(150, 250)],
                             test_keys[0], [subscription],
                             return_urlsafe_keys=False)
    response = self.testapp.get('/alerts_skia_by_bug_id?bug_id=123&host=%s' %
                                SKIA_EXTERNAL_HOST)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(2, len(anomaly_list))

  def testGet_WithNoHostParameter_ShowsError_Skia(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    bug_data.Bug.New(project='chromium', bug_id=123).put()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             bug_id=123,
                             return_urlsafe_keys=False)
    self._AddAnomalyEntities([(150, 250)],
                             test_keys[0], [subscription],
                             return_urlsafe_keys=False)
    response = self.testapp.get(
        '/alerts_skia_by_bug_id?bug_id=123', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIn('Host value is missing to load anomalies to Skia.', error)

  def testGet_WithInvalidBugIdParameter_ShowsError_Skia(self):
    response = self.testapp.get(
        '/alerts_skia_by_bug_id?bug_id=foo', expect_errors=True)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertIsNone(anomaly_list)
    error = self.GetJsonValue(response, 'error')
    self.assertIn('Invalid bug ID "foo".', error)

  def testGet_WithNoBugIdParameter_ShowsError_Skia(self):
    response = self.testapp.get('/alerts_skia_by_bug_id', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('No bug id is found from the request.', error)

  # by rev
  def testGet_WithRevParameter_Skia(self):
    # If the rev parameter is given, then all alerts whose revision range
    # includes the given revision should be included.
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(190, 210), (200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             return_urlsafe_keys=False)
    response = self.testapp.get('/alerts/skia/rev/200?host=%s' %
                                SKIA_INTERNAL_HOST)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(3, len(anomaly_list))
    expected_selected_keys = self.GetJsonValue(response, 'selected_keys')
    self.assertEqual(None, expected_selected_keys)

  def testGet_WithInvalidRevParameter_ShowsError_Skia(self):
    response = self.testapp.get('/alerts/skia/rev/foo', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('Invalid rev "foo".', error)

  # by group id
  @mock.patch.object(perf_issue_service_client, 'GetAnomaliesByAlertGroupID',
                     mock.MagicMock(return_value=[1, 2, 3]))
  def testGet_WithGroupIdParameter_Skia(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500)],
                             test_keys[0], [subscription],
                             group_id="123")
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.get('/alerts/skia/group_id/123?host=%s' %
                                SKIA_INTERNAL_HOST)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(3, len(anomaly_list))

  @mock.patch.object(perf_issue_service_client, 'GetAnomaliesByAlertGroupID',
                     mock.MagicMock(return_value=[1, 2, 3, '1-2-3']))
  def testGet_WithGroupIdParameterWithNonIntegerAnomalyId_Skia(self):
    subscription = self._Subscription()
    test_keys = self._AddTests()
    self._AddAnomalyEntities([(200, 300), (100, 200), (400, 500), (600, 700)],
                             test_keys[0], [subscription],
                             group_id="123")
    self._AddAnomalyEntities([(150, 250)], test_keys[0], [subscription])
    response = self.testapp.get('/alerts/skia/group_id/123?host=%s' %
                                SKIA_INTERNAL_HOST)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(3, len(anomaly_list))

  def testGet_WithInvalidGroupIdParameter_Skia(self):
    response = self.testapp.get('/alerts/skia/group_id/foo', expect_errors=True)
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertIsNone(anomaly_list)
    error = self.GetJsonValue(response, 'error')
    self.assertEqual('Invalid AlertGroup ID "foo".', error)


if __name__ == '__main__':
  unittest.main()
