# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock
import unittest

import webapp2
import webtest

from dashboard import bug_details
from dashboard import generate_benchmark_health_report
from dashboard.common import stored_object
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import benchmark_health_data
from dashboard.services import google_sheets_service


def _MockGetBugDetails(bug_id):
  if bug_id == 12345:
    return {
        'comments': [1, 2, 3, 4, 5],
        'published': datetime.datetime.now(),
        'state': 'open',
        'status': 'Untriaged',
        'summary': 'Bug 12345',
        'review_urls': ['http://codereview.google.com/foo'],
        'bisects': [],
    }
  elif bug_id == 99999:
    return {
        'comments': [1, 2, 3],
        'published': datetime.datetime.now(),
        'state': 'closed',
        'status': 'Fixed',
        'summary': 'Bug 99999',
        'review_urls': ['http://codereview.google.com/bar'],
        'bisects': [{
            'buildbucket_link': 'http://buildbucket_link.com',
            'metric': 'Total',
            'status': 'completed',
            'bot': 'windows',
        }]
    }


class GenerateBenchmarkHealthReportHandlerTest(testing_common.TestCase):

  def setUp(self):
    super(GenerateBenchmarkHealthReportHandlerTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/generate_benchmark_health_report',
        generate_benchmark_health_report.GenerateBenchmarkHealthReportHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddMockData(self):
    mock_tests = [['ChromiumPerf'], ['windows'], {
        'sunspider': {
            'Total': {},
            'ref': {},
        },
        'page_cycler': {
            'warm': {
                'cnn.com': {},
                'yahoo.com': {},
            }
        }
    }]
    testing_common.AddTests(*mock_tests)
    test_suites = {
        'sunspider': {
            'mon': ['Total'],
            'mas': {'ChromiumPerf': {'windows': False}},
        },
        'page_cycler': {
            'mon': ['warm/cnn.com'],
            'mas': {'ChromiumPerf': {'windows': False}},
        },
    }
    stored_object.Set('internal_only__list_tests_get_test_suites', test_suites)
    testing_common.AddRows('ChromiumPerf/windows/sunspider/Total', {
        12345: {'timestamp':  datetime.datetime.now(), 'value': 5},
        12344: {
            'timestamp': datetime.datetime.now() - datetime.timedelta(days=10),
            'value': 7
        },
    })
    anomaly.Anomaly(bug_id=None,
                    test=utils.TestKey('ChromiumPerf/windows/sunspider/Total'),
                    is_improvement=False,
                    median_before_anomaly=5,
                    median_after_anomaly=7).put()
    anomaly.Anomaly(bug_id=12345,
                    test=utils.TestKey('ChromiumPerf/windows/sunspider/Total'),
                    is_improvement=False,
                    median_before_anomaly=7,
                    median_after_anomaly=9).put()
    anomaly.Anomaly(bug_id=99999,
                    test=utils.TestKey('ChromiumPerf/windows/sunspider/Total'),
                    is_improvement=False,
                    median_before_anomaly=5,
                    median_after_anomaly=7).put()
    anomaly.Anomaly(bug_id=-1,
                    test=utils.TestKey('ChromiumPerf/windows/sunspider/Total'),
                    is_improvement=False,
                    median_before_anomaly=5,
                    median_after_anomaly=7).put()

  @mock.patch.object(
      google_sheets_service, 'GetRange', mock.MagicMock(return_value=None))
  def testPost_createsNamedReport(self):
    self.testapp.post('/generate_benchmark_health_report', {
        'report_name': 'My cool report',
        'num_days': '90',
        'master': 'Foo'
    })
    report = benchmark_health_data.GetHealthReport('My cool report')
    self.assertEqual('My cool report', report['name'])
    self.assertEqual(90, report['num_days'])
    self.assertEqual('Foo', report['master'])
    self.assertTrue(report['is_complete'])

  @mock.patch.object(
      google_sheets_service, 'GetRange', mock.MagicMock(return_value=None))
  @mock.patch.object(
      generate_benchmark_health_report,
      '_DefaultReportName',
      mock.MagicMock(return_value='DEFAULT NAME'))
  def testPost_generatesReportName(self):
    self._AddMockData()
    self.testapp.post('/generate_benchmark_health_report', {
        'num_days': '10',
    })
    reports = benchmark_health_data.BenchmarkHealthReport.query().fetch()
    self.assertEqual(1, len(reports))
    report = reports[0].GetReport()
    self.assertEqual('DEFAULT NAME', report['name'])
    self.assertEqual(10, report['num_days'])
    self.assertEqual('ChromiumPerf', report['master'])
    print reports[0].expected_num_benchmarks
    self.assertFalse(report['is_complete'])

  @mock.patch.object(
      google_sheets_service, 'GetRange', mock.MagicMock(return_value=None))
  @mock.patch.object(
      bug_details, 'GetBugDetails',
      side_effect=_MockGetBugDetails)
  def testPost_TwoBenchmarksInDatastore(self, _):
    self._AddMockData()
    self.testapp.post('/generate_benchmark_health_report', {
        'report_name': 'My report',
    })
    self.ExecuteTaskQueueTasks(
        '/generate_benchmark_health_report',
        generate_benchmark_health_report._TASK_QUEUE_NAME)
    reports = benchmark_health_data.BenchmarkHealthReport.query().fetch()
    self.assertEqual(1, len(reports))
    self.assertEqual('My report', reports[0].key.string_id())
    benchmarks = benchmark_health_data.BenchmarkHealthData.query(
        ancestor=reports[0].key).fetch()
    self.assertEqual(2, len(benchmarks))
    self.assertEqual('page_cycler', benchmarks[0].name)
    self.assertEqual('sunspider', benchmarks[1].name)
    self.assertEqual(0, len(benchmarks[0].alerts))
    self.assertEqual(0, len(benchmarks[0].bisects))
    self.assertEqual(0, len(benchmarks[0].bots))
    self.assertEqual(0, len(benchmarks[0].bugs))
    self.assertEqual(0, len(benchmarks[0].reviews))
    self.assertEqual(4, len(benchmarks[1].alerts))
    self.assertEqual(1, len(benchmarks[1].bisects))
    self.assertEqual(1, len(benchmarks[1].bots))
    self.assertEqual('windows', benchmarks[1].bots[0].name)
    self.assertEqual('windows', benchmarks[1].bots[0].platform)
    seconds_since_last_update = (
        datetime.datetime.now() -
        benchmarks[1].bots[0].last_update).total_seconds()
    self.assertLess(seconds_since_last_update, 1000)
    self.assertEqual(2, len(benchmarks[1].reviews))

  @mock.patch.object(
      google_sheets_service, 'GetRange', mock.MagicMock(return_value=[
          ['sunspider', 'foo@chromium.org'],
          ['page_cycler', 'bar@chromium.org'],
          ['smoothness', 'baz@chromium.org']
      ]))
  @mock.patch.object(
      bug_details, 'GetBugDetails',
      side_effect=_MockGetBugDetails)
  def testPost_BenchmarksInSheetNotInDatastore(self, _):
    self._AddMockData()
    self.testapp.post('/generate_benchmark_health_report', {
        'report_name': 'My report',
    })
    self.ExecuteTaskQueueTasks(
        '/generate_benchmark_health_report',
        generate_benchmark_health_report._TASK_QUEUE_NAME)
    reports = benchmark_health_data.BenchmarkHealthReport.query().fetch()
    self.assertEqual(1, len(reports))
    benchmarks = benchmark_health_data.BenchmarkHealthData.query(
        ancestor=reports[0].key).fetch()
    self.assertEqual(3, len(benchmarks))
    self.assertEqual('page_cycler', benchmarks[0].name)
    self.assertEqual('bar@chromium.org', benchmarks[0].owner)
    self.assertTrue(benchmarks[0].no_data_on_dashboard)
    self.assertEqual('smoothness', benchmarks[1].name)
    self.assertEqual('baz@chromium.org', benchmarks[1].owner)
    self.assertTrue(benchmarks[1].no_data_on_dashboard)
    self.assertEqual('sunspider', benchmarks[2].name)
    self.assertEqual('foo@chromium.org', benchmarks[2].owner)
    self.assertFalse(benchmarks[2].no_data_on_dashboard)


if __name__ == '__main__':
  unittest.main()
