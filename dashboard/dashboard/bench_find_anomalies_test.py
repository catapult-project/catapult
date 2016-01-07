# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from mapreduce import test_support
import mock

from google.appengine.ext import testbed

from dashboard import bench_find_anomalies
from dashboard import find_change_points_exp
from dashboard import layered_cache
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import anomaly_config
from dashboard.models import graph_data
from dashboard.models import sheriff

_SAMPLE_SERIES = [
    (1, 50.0), (2, 50.0), (3, 50.0),
    (4, 60.0), (5, 60.0), (6, 60.0),
    (7, 50.0), (8, 50.0), (9, 50.0),
    (10, 50.0), (11, 50.0), (12, 50.0)]

_LARGE_SAMPLE_SERIES = [
    (1, 50.0), (2, 50.0), (3, 50.0), (4, 60.0), (5, 60.0), (6, 60.0),
    (7, 80.0), (8, 80.0), (9, 80.0), (10, 80.0), (11, 80.0), (12, 80.0),
    (13, 90.0), (14, 90.0), (15, 90.0), (16, 50.0), (17, 50.0), (18, 50.0)]


class BenchFindChangePointsTest(testing_common.TestCase):

  def setUp(self):
    super(BenchFindChangePointsTest, self).setUp()
    self.sheriff = sheriff.Sheriff(
        email='a@google.com', id=bench_find_anomalies._TEST_DATA_SHERIFF).put()

  def _AddTestData(self, test_name, rows,
                   improvement_direction=anomaly.UNKNOWN, config=None):
    testing_common.AddTests(
        ['ChromiumGPU'],
        ['linux-release'], {
            'scrolling_benchmark': {
                test_name: {},
            },
        })
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/' + test_name).get()
    test.improvement_direction = improvement_direction
    test_container_key = utils.GetTestContainerKey(test.key)

    sheriff_entity = self.sheriff.get()
    if sheriff_entity.patterns:
      sheriff_entity.patterns.append(test.test_path)
    else:
      sheriff_entity.patterns = [test.test_path]
    sheriff_entity.put()

    for row in rows:
      graph_data.Row(id=row[0], value=row[1], parent=test_container_key).put()

    # Add test config.
    if not config:
      config = {
          'max_window_size': 50,
          'multiple_of_std_dev': 3.5,
          'min_relative_change': 0.1,
          'min_absolute_change': 1.0,
          'min_segment_size': 3,
      }
    anomaly_config.AnomalyConfig(
        id='config_' + test_name, config=config,
        patterns=[test.test_path]).put()

    test.put()
    return test

  def _AddAnomalyForTest(self, end_revision, bug_id, test_key):
    anomaly_key = anomaly.Anomaly(
        start_revision=end_revision - 1,
        end_revision=end_revision,
        test=test_key,
        median_before_anomaly=50,
        segment_size_after=3,
        window_end_revision=6,
        std_dev_before_anomaly=10,
        bug_id=bug_id,
        sheriff=self.sheriff).put()
    return anomaly_key

  @mock.patch.object(bench_find_anomalies, '_AddReportToLog')
  def testBenchFindChangePoints_Basic(self, add_report_to_log_mock):
    test = self._AddTestData('test', _SAMPLE_SERIES, anomaly.DOWN)

    # Add untriaged anomalies.
    self._AddAnomalyForTest(7, None, test.key)

    # Add confirmed anomalies.
    self._AddAnomalyForTest(4, 123, test.key)

    # Add invalid anomalies.
    self._AddAnomalyForTest(10, -1, test.key)

    bench_find_anomalies.SetupBaseDataForBench()

    self.ExecuteDeferredTasks(bench_find_anomalies._TASK_QUEUE_NAME)

    test_benches = bench_find_anomalies.TestBench.query().fetch()
    self.assertEqual(1, len(test_benches))

    self.assertEqual(_SAMPLE_SERIES, test_benches[0].data_series)
    self.assertEqual([[1, 2, 3, 4, 5, 6, 7, 8]],
                     test_benches[0].base_anomaly_revs)
    self.assertEqual([[6, 7, 8, 9, 10, 11, 12]],
                     test_benches[0].invalid_anomaly_revs)
    self.assertEqual([[1, 2, 3, 4, 5, 6, 7, 8]],
                     test_benches[0].confirmed_anomaly_revs)

    bench_name = 'find_change_points_default'
    bench_description = 'A description.'
    bench_find_anomalies.BenchFindChangePoints(bench_name, bench_description)

    # Layered cache set.
    bench_key = '%s.%s' % (bench_name, bench_description)
    self.assertEqual({bench_key: True}, layered_cache.Get(
        bench_find_anomalies._FIND_ANOMALIES_BENCH_CACHE_KEY))

    task_queue = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    test_support.execute_until_empty(task_queue,
                                     bench_find_anomalies._TASK_QUEUE_NAME)

    expected_result_dict = {
        'bench_name': bench_name,
        'description': bench_description,
        'invalid_alerts': '0/1',
        'confirmed_alerts': '1/1',
        'new_alerts': 0,
        'total_alerts': '1/1',
        'unconfirmed_alert_links': '',
        'extra_alert_links': '',
    }
    add_report_to_log_mock.assert_called_once_with(expected_result_dict)

  def testBenchFindChangePoints_UniqueBenchRunsOnce(self):
    test = self._AddTestData('test', _SAMPLE_SERIES, anomaly.DOWN)
    self._AddAnomalyForTest(4, 123, test.key)

    bench_find_anomalies.SetupBaseDataForBench()

    self.ExecuteDeferredTasks(bench_find_anomalies._TASK_QUEUE_NAME)

    bench_name = 'a_bench_name1'
    bench_description = 'Test find_change_points v1'
    bench_find_anomalies._EXPERIMENTAL_FUNCTIONS = {
        bench_name: find_change_points_exp.RunFindChangePoints
    }

    bench_find_anomalies.BenchFindChangePoints(bench_name, bench_description)

    # A task should be added.
    task_queue = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = task_queue.GetTasks(bench_find_anomalies._TASK_QUEUE_NAME)
    self.assertEqual(1, len(tasks))

    with self.assertRaises(ValueError):
      bench_find_anomalies.BenchFindChangePoints(bench_name, bench_description)


if __name__ == '__main__':
  unittest.main()
