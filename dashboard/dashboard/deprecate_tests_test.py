# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import unittest

import webapp2
import webtest

from dashboard import deprecate_tests
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import graph_data
from dashboard.models import sheriff
from dashboard.models import stoppage_alert


_DEPRECATE_DAYS = deprecate_tests._DEPRECATION_REVISION_DELTA.days + 1

_REMOVAL_DAYS = deprecate_tests._REMOVAL_REVISON_DELTA.days + 1

_TESTS_SIMPLE = [
    ['ChromiumPerf'],
    ['mac'],
    {
        'SunSpider': {
            'Total': {
                't': {},
                't_ref': {},
            },
        }
    }
]

_TESTS_MULTIPLE = [
    ['ChromiumPerf'],
    ['mac'],
    {
        'SunSpider': {
            'Total': {
                't': {},
                't_ref': {},
            },
        },
        'OtherTest': {
            'OtherMetric': {
                'foo1': {},
                'foo2': {},
            },
        },
    }
]


class DeprecateTestsTest(testing_common.TestCase):

  def setUp(self):
    super(DeprecateTestsTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/deprecate_tests', deprecate_tests.DeprecateTestsHandler)])
    self.testapp = webtest.TestApp(app)

    deprecate_tests._DEPRECATE_TESTS_PARALLEL_SHARDS = 2

  def _AddMockRows(self, test_path, age):
    """Adds sample TestMetadata and Row entities."""

    # Add 50 Row entities to some of the tests.
    ts = datetime.datetime.now() - datetime.timedelta(days=age)
    data = {}
    for i in range(15000, 15100, 2):
      data[i] = {'value': 1, 'timestamp': ts}

    testing_common.AddRows(test_path, data)

  def AssertDeprecated(self, test_path, deprecated):
    test_key = utils.TestKey(test_path)
    test = test_key.get()

    self.assertEqual(test.deprecated, deprecated)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest(self, mock_delete):
    testing_common.AddTests(*_TESTS_MULTIPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo1', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo2', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider', False)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', False)

    self.assertFalse(mock_delete.called)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTestDeprecatesSuite(self, mock_delete):
    testing_common.AddTests(*_TESTS_MULTIPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo1', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo2', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    # Do a second pass to catch the suite
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', True)

    self.assertFalse(mock_delete.called)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DoesNotDeleteRowsWithChildren(self, mock_delete):
    testing_common.AddTests(*_TESTS_SIMPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total', _REMOVAL_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', 0)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    # Do a second pass to catch the suite
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider', False)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', False)

    self.assertFalse(mock_delete.called)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTestDeletesData(self, mock_delete):
    testing_common.AddTests(*_TESTS_MULTIPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _REMOVAL_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo1', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo2', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    test = utils.TestKey('ChromiumPerf/mac/SunSpider/Total/t').get()
    mock_delete.assert_called_once_with(test)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeletesTestsWithNoRowsOrChildren(self, mock_delete):
    testing_common.AddTests(*_TESTS_MULTIPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo1', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo2', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    test = utils.TestKey('ChromiumPerf/mac/SunSpider/Total/t_ref').get()
    mock_delete.assert_called_once_with(test)

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_BasicCreatesStoppageAlert(self, mock_delete):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org',
        patterns=['*/*/*/*', '*/*/*/*/*'],
        stoppage_alert_delay=1).put()

    testing_common.AddTests(*_TESTS_MULTIPLE)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo1', 0)
    self._AddMockRows('ChromiumPerf/mac/OtherTest/OtherMetric/foo2', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', True)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(1, len(alerts))

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_RefTest_NoAlert(self, mock_delete):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org',
        patterns=['*/*/*/*', '*/*/*/*/*'],
        stoppage_alert_delay=1).put()

    testing_common.AddTests(*_TESTS_SIMPLE)

    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', 0)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', _DEPRECATE_DAYS)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', True)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(0, len(alerts))

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_NegStoppageDelay_NoAlert(self, mock_delete):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org',
        patterns=['*/*/*/*', '*/*/*/*/*'],
        stoppage_alert_delay=-1).put()

    testing_common.AddTests(*_TESTS_SIMPLE)

    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', _DEPRECATE_DAYS)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', True)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(0, len(alerts))

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_NoSheriff_NoAlert(self, mock_delete):
    testing_common.AddTests(*_TESTS_SIMPLE)

    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', False)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(0, len(alerts))

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_HighStoppageDelay_NoAlert(self, mock_delete):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org',
        patterns=['*/*/*/*', '*/*/*/*/*'],
        stoppage_alert_delay=_DEPRECATE_DAYS+1).put()

    testing_common.AddTests(*_TESTS_SIMPLE)

    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)
    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', False)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(0, len(alerts))

  @mock.patch.object(deprecate_tests, '_AddDeleteTestDataTask')
  def testPost_DeprecateOldTest_ExistingStoppageAlert_NoAlert(
      self, mock_delete):
    sheriff.Sheriff(
        id='ref_sheriff', email='a@chromium.org',
        patterns=['*/*/*/*', '*/*/*/*/*'],
        stoppage_alert_delay=1).put()

    testing_common.AddTests(*_TESTS_SIMPLE)

    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t', _DEPRECATE_DAYS)
    self._AddMockRows('ChromiumPerf/mac/SunSpider/Total/t_ref', 0)

    test_path = 'ChromiumPerf/mac/SunSpider/Total/t'
    test_key = utils.TestKey(test_path)
    test_parent = utils.OldStyleTestKey(test_key)
    query = graph_data.Row.query(graph_data.Row.parent_test == test_parent)
    query = query.order(-graph_data.Row.timestamp)
    last_row = query.get()

    stoppage_alert.CreateStoppageAlert(test_key.get(), last_row).put()

    self.testapp.post('/deprecate_tests')
    self.ExecuteTaskQueueTasks(
        '/deprecate_tests', deprecate_tests._DEPRECATE_TESTS_TASK_QUEUE_NAME)

    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t', True)
    self.AssertDeprecated('ChromiumPerf/mac/SunSpider/Total/t_ref', False)

    self.assertFalse(mock_delete.called)

    alerts = stoppage_alert.StoppageAlert.query().fetch()
    self.assertEqual(1, len(alerts))


if __name__ == '__main__':
  unittest.main()
