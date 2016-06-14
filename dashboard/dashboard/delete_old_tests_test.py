# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest

import webapp2
import webtest

from dashboard import delete_old_tests
from dashboard import delete_test_data
from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data

# Masters, bots and test names to add to the mock datastore.
_MOCK_DATA = [
    ['ChromiumPerf', 'ChromiumWebkit'],
    ['win7', 'mac'],
    {
        'SunSpider': {
            'Total': {
                't': {},
                't_ref': {},
                't_extwr': {},
            },
            '3d-cube': {'t': {}},
        },
        'moz': {
            'read_op_b': {'r_op_b': {}},
        },
    }
]

_TESTS_WITH_NEW_ROWS = [
    'ChromiumPerf/mac/SunSpider/Total/t',
    'ChromiumPerf/mac/moz',
    'ChromiumPerf/win7/SunSpider/3d-cube',
]

_TESTS_WITH_OLD_ROWS = [
    'ChromiumPerf/mac/SunSpider/3d-cube/t',
    'ChromiumPerf/win7/SunSpider/Total/t',
    'ChromiumPerf/win7/moz/read_op_b/r_op_b',
]

class DeleteOldTestsTest(testing_common.TestCase):

  def setUp(self):
    super(DeleteOldTestsTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/delete_old_tests', delete_old_tests.DeleteOldTestsHandler),
        ('/delete_test_data', delete_test_data.DeleteTestDataHandler)])
    self.testapp = webtest.TestApp(app)

  def _AddMockData(self):
    """Adds sample TestMetadata and Row entities."""
    testing_common.AddTests(*_MOCK_DATA)

    recent = datetime.timedelta(days=5)
    for test_path in _TESTS_WITH_NEW_ROWS:
      testing_common.AddRows(
          test_path,
          {x: {'timestamp': datetime.datetime.now() - recent} for x in range(
              15000, 15100, 2)})

    too_long = datetime.timedelta(days=190)
    for test_path in _TESTS_WITH_OLD_ROWS:
      testing_common.AddRows(
          test_path,
          {x: {'timestamp': datetime.datetime.now() - too_long} for x in range(
              15000, 15100, 2)})

  def _AssertExists(self, test_paths):
    for test_path in test_paths:
      test_key = utils.TestKey(test_path)
      if test_path in _TESTS_WITH_NEW_ROWS:
        num_rows = graph_data.Row.query(
            graph_data.Row.parent_test == utils.OldStyleTestKey(test_key)
            ).count()
        self.assertEqual(50, num_rows)
      self.assertIsNotNone(test_key.get())

  def _AssertNotExists(self, test_paths):
    for test_path in test_paths:
      test_key = utils.TestKey(test_path)
      num_rows = graph_data.Row.query(
          graph_data.Row.parent_test == utils.OldStyleTestKey(test_key)).count()
      self.assertEqual(0, num_rows)
      self.assertIsNone(test_key.get())

  def testPost(self):
    self._AddMockData()
    self.testapp.post('/delete_old_tests')
    self.ExecuteTaskQueueTasks(
        '/delete_old_tests', delete_old_tests._TASK_QUEUE_NAME)
    self.ExecuteTaskQueueTasks(
        '/delete_test_data', delete_test_data._TASK_QUEUE_NAME)
    self._AssertNotExists(_TESTS_WITH_OLD_ROWS)
    self._AssertExists(_TESTS_WITH_NEW_ROWS)


if __name__ == '__main__':
  unittest.main()
