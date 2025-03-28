# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
from flask import Flask
import json
from unittest import mock
import sys
import unittest
import webtest

from dashboard import alerts
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import bug_data
from dashboard.models.subscription import Subscription
from dashboard.sheriff_config_client import SheriffConfigClient
from dashboard.sheriff_config_client import InternalServerError

flask_app = Flask(__name__)


@flask_app.route('/alerts', methods=['GET'])
def AlertsHandlerGet():
  return alerts.AlertsHandlerGet()


@flask_app.route('/alerts', methods=['POST'])
def AlertsHandlerPost():
  return alerts.AlertsHandlerPost()


@flask_app.route('/alerts_skia', methods=['GET'])
def SkiaAlertsHandlerGet():
  return alerts.SkiaAlertsHandlerGet()


@flask_app.route('/sheriff_configs_skia', methods=['GET'])
def SkiaLoadSheriffConfigsHandlerGet():
  return alerts.SkiaLoadSheriffConfigsHandlerGet()


@mock.patch.object(SheriffConfigClient, '__init__',
                   mock.MagicMock(return_value=None))
class AlertsTest(testing_common.TestCase):

  def setUp(self):
    super().setUp()
    self.testapp = webtest.TestApp(flask_app)
    testing_common.SetSheriffDomains(['chromium.org'])
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    self.SetCurrentUser('internal@chromium.org', is_admin=True)

  def _AddAlertsToDataStore(self):
    """Adds sample data, including triaged and non-triaged alerts."""
    key_map = {}

    subscription = Subscription(
        name='Chromium Perf Sheriff',
        notification_email='internal@chromium.org',
        bug_components=['Mock Component'],
        bug_labels=['test bug', 'mocked'],
        bug_cc_emails=['this@chromium.org', 'that@google.com'])
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'], {
            'scrolling-benchmark': {
                'first_paint': {},
                'first_paint_ref': {},
                'mean_frame_time': {},
                'mean_frame_time_ref': {},
            }
        })
    first_paint = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling-benchmark/first_paint')
    mean_frame_time = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time')

    # By default, all TestMetadata entities have an improvement_direction of
    # UNKNOWN, meaning that neither direction is considered an improvement.
    # Here we set the improvement direction so that some anomalies are
    # considered improvements.
    for test_key in [first_paint, mean_frame_time]:
      test = test_key.get()
      test.improvement_direction = anomaly.DOWN
      test.put()

    # Add some (12) non-triaged alerts.
    # The first (4) of them are internal_only
    for end_rev in range(10000, 10120, 10):
      test_key = first_paint if end_rev % 20 == 0 else mean_frame_time
      internal = end_rev < 10000 + 40
      ref_test_key = utils.TestKey('%s_ref' % utils.TestPath(test_key))
      anomaly_entity = anomaly.Anomaly(
          start_revision=end_rev - 5,
          end_revision=end_rev,
          display_start=end_rev - 5 - 1,
          display_end=end_rev + 1,
          test=test_key,
          median_before_anomaly=100,
          median_after_anomaly=200,
          ref_test=ref_test_key,
          subscriptions=[subscription],
          subscription_names=[subscription.name],
          internal_only=internal,
      )
      anomaly_entity.SetIsImprovement()
      anomaly_key = anomaly_entity.put()
      key_map[end_rev] = anomaly_key.urlsafe()
      # set one of the anomaly which is detected before the skia limit.
      if end_rev == 10000:
        anomaly_entity.timestamp = datetime.datetime.strptime(
            '2022-6-1T0:0:0', '%Y-%m-%dT%H:%M:%S')

    # Add some (2) already-triaged alerts.
    for end_rev in range(10120, 10140, 10):
      test_key = first_paint if end_rev % 20 == 0 else mean_frame_time
      ref_test_key = utils.TestKey('%s_ref' % utils.TestPath(test_key))
      bug_id = -1 if end_rev % 20 == 0 else 12345
      anomaly_entity = anomaly.Anomaly(
          start_revision=end_rev - 5,
          end_revision=end_rev,
          test=test_key,
          median_before_anomaly=100,
          median_after_anomaly=200,
          ref_test=ref_test_key,
          bug_id=bug_id,
          subscriptions=[subscription],
          subscription_names=[subscription.name],
      )
      anomaly_entity.SetIsImprovement()
      anomaly_key = anomaly_entity.put()
      key_map[end_rev] = anomaly_key.urlsafe()
      if bug_id > 0:
        bug_data.Bug.New(project='chromium', bug_id=bug_id).put()

    # Add some (6) non-triaged improvements.
    for end_rev in range(10140, 10200, 10):
      test_key = mean_frame_time
      ref_test_key = utils.TestKey('%s_ref' % utils.TestPath(test_key))
      anomaly_entity = anomaly.Anomaly(
          start_revision=end_rev - 5,
          end_revision=end_rev,
          test=test_key,
          median_before_anomaly=200,
          median_after_anomaly=100,
          ref_test=ref_test_key,
          subscriptions=[subscription],
          subscription_names=[subscription.name],
      )
      anomaly_entity.SetIsImprovement()
      anomaly_key = anomaly_entity.put()
      self.assertTrue(anomaly_entity.is_improvement)
      key_map[end_rev] = anomaly_key.urlsafe()
    return key_map

  def testV2(self):
    alert = anomaly.Anomaly(
        bug_id=10,
        end_revision=20,
        internal_only=True,
        is_improvement=True,
        median_after_anomaly=30,
        median_before_anomaly=40,
        recovered=True,
        subscription_names=['Sheriff2'],
        subscriptions=[
            Subscription(
                name='Sheriff2',
                bug_components=['component'],
                notification_email='sullivan@google.com')
        ],
        start_revision=5,
        test=utils.TestKey('m/b/s/m/c'),
        units='ms',
    ).put().get()
    actual = alerts.GetAnomalyDict(alert, v2=True)
    del actual['dashboard_link']
    self.assertCountEqual(
        {
            'bug_components': ['component'],
            'bug_id': 10,
            'project_id': 'chromium',
            'bug_labels': ['Restrict-View-Google'],
            'descriptor': {
                'testSuite': 's',
                'measurement': 'm',
                'bot': 'm:b',
                'testCase': 'c',
                'statistic': None,
            },
            'end_revision': 20,
            'improvement': True,
            'key': alert.key.urlsafe(),
            'median_after_anomaly': 30,
            'median_before_anomaly': 40,
            'new_url': '',
            'recovered': True,
            'start_revision': 5,
            'units': 'ms',
            'pinpoint_bisects': [],
        }, actual)

  def testGet(self):
    response = self.testapp.get('/alerts')
    self.assertEqual('text/html', response.content_type)
    self.assertIn(b'Chrome Performance Alerts', response.body)

  def testPost_NoParametersSet_UntriagedAlertsListed(self):
    key_map = self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts')
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(12, len(anomaly_list))
    # The test below depends on the order of the items, but the order is not
    # guaranteed; it depends on the timestamps, which depend on put order.
    anomaly_list.sort(key=lambda a: -a['end_revision'])
    expected_end_rev = 10110
    for alert in anomaly_list:
      self.assertEqual(expected_end_rev, alert['end_revision'])
      self.assertEqual(expected_end_rev - 5, alert['start_revision'])
      self.assertEqual(key_map[expected_end_rev].decode(), alert['key'])
      self.assertEqual('ChromiumGPU', alert['master'])
      self.assertEqual('linux-release', alert['bot'])
      self.assertEqual('scrolling-benchmark', alert['testsuite'])
      if expected_end_rev % 20 == 0:
        self.assertEqual('first_paint', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/first_paint_ref',
            alert['ref_test'])
      else:
        self.assertEqual('mean_frame_time', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time_ref',
            alert['ref_test'])
      self.assertEqual('100.0%', alert['percent_changed'])
      self.assertIsNone(alert['bug_id'])
      expected_end_rev -= 10
    self.assertEqual(expected_end_rev, 9990)

  @unittest.skipIf(sys.platform.startswith('win'), 'bad mock datastore')
  def testPost_TriagedParameterSet_TriagedListed(self):
    self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts', {'triaged': 'true'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    # The alerts listed should contain those added above, including alerts
    # that have a bug ID that is not None.
    self.assertEqual(14, len(anomaly_list))
    expected_end_rev = 10130
    # The test below depends on the order of the items, but the order is not
    # guaranteed; it depends on the timestamps, which depend on put order.
    anomaly_list.sort(key=lambda a: -a['end_revision'])
    for alert in anomaly_list:
      if expected_end_rev == 10130:
        self.assertEqual(12345, alert['bug_id'])
      elif expected_end_rev == 10120:
        self.assertEqual(-1, alert['bug_id'])
      else:
        self.assertIsNone(alert['bug_id'])
      expected_end_rev -= 10
    self.assertEqual(expected_end_rev, 9990)

  def testPost_ImprovementsParameterSet_ListsImprovements(self):
    self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts', {'improvements': 'true'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(18, len(anomaly_list))
    for alert in anomaly_list:
      if alert['end_revision'] >= 10140:
        self.assertEqual(alert['improvement'], True)

  def testPost_SheriffParameterSet_OtherSheriffAlertsListed(self):
    self._AddAlertsToDataStore()
    subscription = Subscription(
        name='Chromium Perf Sheriff',
        notification_email='sullivan@google.com',
    )
    mean_frame_time = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time')
    anomalies, _, _ = anomaly.Anomaly.QueryAsync(
        test=mean_frame_time).get_result()
    for anomaly_entity in anomalies:
      anomaly_entity.subscriptions = [subscription]
      anomaly_entity.subscription_names = [subscription.name]
      anomaly_entity.put()

    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                ),
                Subscription(
                    name='Sheriff2',
                    notification_email='sullivan@google.com',
                )
            ], None))):
      response = self.testapp.post('/alerts', {'sheriff': 'Sheriff2'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    sheriff_list = self.GetJsonValue(response, 'sheriff_list')
    for alert in anomaly_list:
      self.assertEqual('mean_frame_time', alert['test'])
    self.assertEqual(2, len(sheriff_list))
    self.assertEqual('Chromium Perf Sheriff', sheriff_list[0])
    self.assertEqual('Sheriff2', sheriff_list[1])

  def testPost_WithBogusSheriff_HasErrorMessage(self):
    with mock.patch.object(SheriffConfigClient, 'List',
                           mock.MagicMock(return_value=([], None))):
      response = self.testapp.post('/alerts?sheriff=Foo', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIsNotNone(error)

  def testPost_ExternalUserRequestsInternalOnlySheriff_ErrorMessage(self):
    self.UnsetCurrentUser()
    self.assertFalse(utils.IsInternalUser())
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts?sheriff=Foo', expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIsNotNone(error)

  def testPost_AnomalyCursorSet_ReturnsNextCursorAndShowMore(self):
    self._AddAlertsToDataStore()
    # Need to post to the app once to get the initial cursor.
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts', {'max_anomalies_to_show': 5})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    anomaly_cursor = self.GetJsonValue(response, 'anomaly_cursor')

    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.post('/alerts', {
          'anomaly_cursor': anomaly_cursor,
          'max_anomalies_to_show': 5
      })
    anomaly_list2 = self.GetJsonValue(response, 'anomaly_list')
    anomalies_show_more = self.GetJsonValue(response, 'show_more_anomalies')
    anomaly_cursor = self.GetJsonValue(response, 'anomaly_cursor')
    anomaly_count = self.GetJsonValue(response, 'anomaly_count')
    self.assertEqual(5, len(anomaly_list2))
    self.assertTrue(anomalies_show_more)
    self.assertIsNotNone(anomaly_cursor)  # Don't know what this will be.
    self.assertEqual(12, anomaly_count)
    for a in anomaly_list:  # Ensure anomaly_lists aren't equal.
      self.assertNotIn(a, anomaly_list2)

  def testPost_NoParametersSet_UntriagedAlertsListed_External_Skia(self):
    key_map = self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia',
                                  {'host': 'https://perf.luci.app'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(8, len(anomaly_list))
    # The test below depends on the order of the items, but the order is not
    # guaranteed; it depends on the timestamps, which depend on put order.
    anomaly_list.sort(key=lambda a: -a['end_revision'])
    expected_end_rev = 10110
    for alert in anomaly_list:
      self.assertEqual(expected_end_rev + 1, alert['end_revision'])
      self.assertEqual(expected_end_rev - 5 - 1, alert['start_revision'])
      self.assertEqual(key_map[expected_end_rev].decode(), alert['key'])
      self.assertEqual('ChromiumGPU', alert['master'])
      self.assertEqual('linux-release', alert['bot'])
      self.assertEqual('scrolling-benchmark', alert['testsuite'])
      self.assertEqual('Chromium Perf Sheriff', alert['subscription_name'])
      self.assertEqual('Mock Component', alert['bug_component'])
      self.assertEqual(['test bug', 'mocked'], alert['bug_labels'])
      self.assertEqual(['this@chromium.org', 'that@google.com'],
                       alert['bug_cc_emails'])
      if expected_end_rev % 20 == 0:
        self.assertEqual('first_paint', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/first_paint_ref',
            alert['ref_test'])
      else:
        self.assertEqual('mean_frame_time', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time_ref',
            alert['ref_test'])
      self.assertEqual('100.0%', alert['percent_changed'])
      self.assertIsNone(alert['bug_id'])
      expected_end_rev -= 10
    self.assertEqual(expected_end_rev, 10030)

  def testPost_NoParametersSet_UntriagedAlertsListed_Internal_Skia(self):
    key_map = self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia',
                                  {'host': 'https://chrome-perf.corp.goog'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    # one of them (ending at 10000) is older then 2022/7/1 and thus will not
    # be reported in Skia.
    self.assertEqual(4 + 8 - 1, len(anomaly_list))
    # The test below depends on the order of the items, but the order is not
    # guaranteed; it depends on the timestamps, which depend on put order.
    anomaly_list.sort(key=lambda a: -a['end_revision'])
    expected_end_rev = 10110
    for alert in anomaly_list:
      self.assertTrue('test_path' in alert)
      self.assertEqual(expected_end_rev + 1, alert['end_revision'])
      self.assertEqual(expected_end_rev - 5 - 1, alert['start_revision'])
      self.assertEqual(key_map[expected_end_rev].decode(), alert['key'])
      self.assertEqual('ChromiumGPU', alert['master'])
      self.assertEqual('linux-release', alert['bot'])
      self.assertEqual('scrolling-benchmark', alert['testsuite'])
      self.assertEqual('Chromium Perf Sheriff', alert['subscription_name'])
      self.assertEqual('Mock Component', alert['bug_component'])
      self.assertEqual(['test bug', 'mocked'], alert['bug_labels'])
      self.assertEqual(['this@chromium.org', 'that@google.com'],
                       alert['bug_cc_emails'])
      if expected_end_rev % 20 == 0:
        self.assertEqual('first_paint', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/first_paint_ref',
            alert['ref_test'])
      else:
        self.assertEqual('mean_frame_time', alert['test'])
        self.assertEqual(
            'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time_ref',
            alert['ref_test'])
      self.assertEqual('100.0%', alert['percent_changed'])
      self.assertIsNone(alert['bug_id'])
      expected_end_rev -= 10
    self.assertEqual(expected_end_rev, 10000)

  def testPost_NoParametersSet_UntriagedAlertsListed_NoAnomalyForMaster(self):
    self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia',
                                  {'host': 'https://webrtc-perf.luci.app'})
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(0, len(anomaly_list))

  @unittest.skipIf(sys.platform.startswith('win'), 'bad mock datastore')
  def testPost_TriagedParameterSet_TriagedListed_Skia(self):
    self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia', {
          'host': 'https://perf.luci.app',
          'triaged': 'true'
      })
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    # The alerts listed should contain those added above, including alerts
    # that have a bug ID that is not None.
    self.assertEqual(8 + 2, len(anomaly_list))
    expected_end_rev = 10130
    # The test below depends on the order of the items, but the order is not
    # guaranteed; it depends on the timestamps, which depend on put order.
    anomaly_list.sort(key=lambda a: -a['end_revision'])
    for alert in anomaly_list:
      if expected_end_rev == 10130:
        self.assertEqual(12345, alert['bug_id'])
      elif expected_end_rev == 10120:
        self.assertEqual(-1, alert['bug_id'])
      else:
        self.assertIsNone(alert['bug_id'])
      expected_end_rev -= 10
    self.assertEqual(expected_end_rev, 10030)

  def testPost_ImprovementsParameterSet_ListsImprovements_Skia(self):
    self._AddAlertsToDataStore()
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia', {
          'host': 'https://perf.luci.app',
          'improvements': 'true'
      })
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    self.assertEqual(8 + 6, len(anomaly_list))
    for alert in anomaly_list:
      if alert['end_revision'] >= 10140:
        self.assertEqual(alert['is_improvement'], True)

  def testPost_SheriffParameterSet_OtherSheriffAlertsListed_Skia(self):
    self._AddAlertsToDataStore()
    subscription = Subscription(
        name='Chromium Perf Sheriff',
        notification_email='sullivan@google.com',
    )
    mean_frame_time = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling-benchmark/mean_frame_time')
    anomalies, _, _ = anomaly.Anomaly.QueryAsync(
        test=mean_frame_time).get_result()
    for anomaly_entity in anomalies:
      anomaly_entity.subscriptions = [subscription]
      anomaly_entity.subscription_names = [subscription.name]
      anomaly_entity.put()

    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                ),
                Subscription(
                    name='Sheriff2',
                    notification_email='sullivan@google.com',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia', {
          'host': 'https://perf.luci.app',
          'sheriff': 'Sheriff2'
      })
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    for alert in anomaly_list:
      self.assertEqual('mean_frame_time', alert['test'])

  def testPost_WithBogusSheriff_HasErrorMessage_Skia(self):
    with mock.patch.object(SheriffConfigClient, 'List',
                           mock.MagicMock(return_value=([], None))):
      response = self.testapp.get(
          '/alerts_skia', {
              'host': 'https://perf.luci.app',
              'sheriff': 'Foo'
          },
          expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIsNotNone(error)

  def testPost_ExternalUserRequestsInternalOnlySheriff_ErrorMessage_Skia(self):
    self.UnsetCurrentUser()
    self.assertFalse(utils.IsInternalUser())
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get(
          '/alerts_skia', {
              'host': 'https://perf.luci.app',
              'sheriff': 'Foo'
          },
          expect_errors=True)
    error = self.GetJsonValue(response, 'error')
    self.assertIsNotNone(error)

  def testPost_AnomalyCursorSet_ReturnsNextCursorAndShowMore_Skia(self):
    self._AddAlertsToDataStore()
    # Need to post to the app once to get the initial cursor.
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get('/alerts_skia', {
          'host': 'https://perf.luci.app',
          'max_anomalies_to_show': 5
      })
    anomaly_list = self.GetJsonValue(response, 'anomaly_list')
    anomaly_cursor = self.GetJsonValue(response, 'anomaly_cursor')

    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(
                    name='Chromium Perf Sheriff',
                    notification_email='internal@chromium.org',
                )
            ], None))):
      response = self.testapp.get(
          '/alerts_skia', {
              'host': 'https://perf.luci.app',
              'anomaly_cursor': anomaly_cursor,
              'max_anomalies_to_show': 5
          })
    anomaly_list2 = self.GetJsonValue(response, 'anomaly_list')
    anomaly_cursor = self.GetJsonValue(response, 'anomaly_cursor')
    self.assertEqual(3, len(anomaly_list2))
    self.assertIsNotNone(anomaly_cursor)  # Don't know what this will be.
    for a in anomaly_list:  # Ensure anomaly_lists aren't equal.
      self.assertNotIn(a, anomaly_list2)

  def testSheriffConfigsGet_Success(self):
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(
            return_value=([
                Subscription(name='Sheriff',),
                Subscription(name='Sheriff V2',)
            ], None))):
      response = self.testapp.get('/sheriff_configs_skia')
      body_json = json.loads(response.body)

      self.assertEqual(2, len(body_json.get('sheriff_list')))
      self.assertEqual(['Sheriff', 'Sheriff V2'], body_json.get('sheriff_list'))

  def testSheriffConfigsGet_Failed(self):
    with mock.patch.object(
        SheriffConfigClient, 'List',
        mock.MagicMock(side_effect=InternalServerError('Mock error'))):
      response = self.testapp.get('/sheriff_configs_skia')
      body_json = json.loads(response.body)

      self.assertEqual('Mock error', body_json.get('error'))

if __name__ == '__main__':
  unittest.main()
