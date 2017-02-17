# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import webapp2
import webtest

from google.appengine.ext import ndb

from dashboard import benchmark_health_report
from dashboard import update_test_suites
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import sheriff


class BenchmarkHealthReportTest(testing_common.TestCase):

  def setUp(self):
    super(BenchmarkHealthReportTest, self).setUp()
    app = webapp2.WSGIApplication(
        [('/benchmark_health_report',
          benchmark_health_report.BenchmarkHealthReportHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddAnomalyEntities(
      self, revision_ranges, test_key, sheriff_key, bug_id=None):
    """Adds a group of Anomaly entities to the datastore."""
    urlsafe_keys = []
    for start_rev, end_rev in revision_ranges:
      anomaly_key = anomaly.Anomaly(
          start_revision=start_rev, end_revision=end_rev,
          test=test_key, bug_id=bug_id, sheriff=sheriff_key,
          median_before_anomaly=100, median_after_anomaly=200).put()
      urlsafe_keys.append(anomaly_key.urlsafe())
    return urlsafe_keys

  def _AddTests(self):
    """Adds sample TestMetadata entities and returns their keys."""
    testing_common.AddTests(['ChromiumPerf'], ['linux'], {
        'sunspider': {
            'Total': {},
            'ref': {},
        },
        'page_cycler': {
            'load_time': {
                'cnn.com': {},
                'google.com': {},
            }
        }
    })
    tests = graph_data.TestMetadata.query()
    for test in tests:
      test.improvement_direction = anomaly.DOWN
    ndb.put_multi(tests)

  def _AddSheriff(self, patterns):
    """Adds a Sheriff entity and returns the key."""
    return sheriff.Sheriff(
        id='Chromium Perf Sheriff',
        email='sullivan@google.com',
        patterns=patterns).put()

  def _AddCachedSuites(self):
    test_suites = {
        'sunspider': {
            'mas': {'ChromiumPerf': {'mac': False, 'linux': False}},
            'mon': ['Total'],
        },
        'page_cycler': {
            'mas': {'ChromiumPerf': {'linux': False}, 'CrOS': {'foo': False}},
            'mon': ['load_time'],
        },
        'speedometer': {
            'mas': {'CrOS': {'foo': False}}
        }
    }
    key = update_test_suites._NamespaceKey(
        update_test_suites._LIST_SUITES_CACHE_KEY)
    stored_object.Set(key, test_suites)

  def testGet(self):
    response = self.testapp.get('/benchmark_health_report')
    self.assertEqual('text/html', response.content_type)
    self.assertIn('Chrome Performance Dashboard', response.body)

  def testPost_MasterArgument_ListsTestsForMaster(self):
    self._AddCachedSuites()
    response = self.testapp.post(
        '/benchmark_health_report', {'master': 'CrOS'})
    benchmark_list = self.GetJsonValue(response, 'benchmarks')
    self.assertItemsEqual(benchmark_list, ['page_cycler', 'speedometer'])

  def testPost_BenchmarkArgument_ListsAlertsAndBots(self):
    self._AddCachedSuites()
    self._AddSheriff(['*/*/page_cycler/*', '*/*/page_cycler/*/*'])
    self._AddTests()
    self._AddAnomalyEntities(
        [(200, 400), (600, 800)],
        utils.TestKey('ChromiumPerf/linux/page_cycler/load_time'),
        ndb.Key('Sheriff', 'Chromium Perf Sheriff'))
    self._AddAnomalyEntities(
        [(500, 700)],
        utils.TestKey('ChromiumPerf/linux/page_cycler/load_time/cnn.com'),
        ndb.Key('Sheriff', 'Chromium Perf Sheriff'))
    response = self.testapp.post(
        '/benchmark_health_report', {
            'benchmark': 'page_cycler',
            'num_days': '30',
            'master': 'ChromiumPerf',
        })
    bots = self.GetJsonValue(response, 'bots')
    self.assertItemsEqual(bots, ['linux'])
    self.assertTrue(self.GetJsonValue(response, 'monitored'))
    alerts = self.GetJsonValue(response, 'alerts')
    self.assertEqual(3, len(alerts))

  def testPost_Benchmark_NotMonitored(self):
    self._AddCachedSuites()
    self._AddTests()
    response = self.testapp.post(
        '/benchmark_health_report', {
            'benchmark': 'page_cycler',
            'num_days': '30',
            'master': 'ChromiumPerf',
        })
    self.assertFalse(self.GetJsonValue(response, 'monitored'))

  def testPost_BenchmarkArgumentNumDaysArgument_ListsCorrectAlerts(self):
    self._AddCachedSuites()
    self._AddSheriff(['*/*/page_cycler/*', '*/*/page_cycler/*/*'])
    self._AddTests()
    self._AddAnomalyEntities(
        [(200, 400), (600, 800)],
        utils.TestKey('ChromiumPerf/linux/page_cycler/load_time'),
        ndb.Key('Sheriff', 'Chromium Perf Sheriff'))
    self._AddAnomalyEntities(
        [(500, 700)],
        utils.TestKey('ChromiumPerf/linux/page_cycler/load_time/cnn.com'),
        ndb.Key('Sheriff', 'Chromium Perf Sheriff'))
    anomalies = anomaly.Anomaly.query().fetch()
    anomalies[0].timestamp = datetime.datetime.now() - datetime.timedelta(
        days=20)
    anomalies[0].put()
    response = self.testapp.post(
        '/benchmark_health_report',
        {'benchmark': 'page_cycler', 'num_days': '5', 'master': 'ChromiumPerf'})
    bots = self.GetJsonValue(response, 'bots')
    self.assertItemsEqual(bots, ['linux'])
    self.assertTrue(self.GetJsonValue(response, 'monitored'))
    alerts = self.GetJsonValue(response, 'alerts')
    self.assertEqual(2, len(alerts))


if __name__ == '__main__':
  unittest.main()
