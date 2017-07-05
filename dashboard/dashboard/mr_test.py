# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import unittest
import webapp2
import webtest

from mapreduce import operation as op

from dashboard import delete_test_data
from dashboard import mr
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly
from dashboard.models import graph_data

# Some sample Tests to add to the mock datastore below.
_TESTS = {
    'suite': {
        'graph_a': {
            'trace_a': {},
        },
        'graph_b': {
            'trace_b': {}
        }
    }
}

_REF_TEST = {
    'suite': {
        'graph_a': {
            'trace_a': {
                'ref': {}
            },
        },
    }
}


class MrTest(testing_common.TestCase):

  def setUp(self):
    super(MrTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/delete_test_data', delete_test_data.DeleteTestDataHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)
    self.PatchDatastoreHooksRequest()

  def _ExecOperation(self, operation):
    """Helper method to run a datastore mutation operation.

    mapreduce.operation.db.Put and mapreduce.operation.db.Delete objects
    are normally executed by calling them with a mapreduce.context.Context
    object as input.

    For convenience in the unit test methods here, we'll just take the entity
    and then call the usual put and delete methods.

    Args:
      operation: A Put or Delete datastore operation object.
    """
    if operation.__class__ == op.db.Put:
      operation.entity.put()
    if operation.__class__ == op.db.Delete:
      operation.entity.key.delete()

  def _AddMockDataForDeprecatedTests(self):
    """Adds some sample data, some of which only has old timestamps."""
    testing_common.AddTests(['ChromiumPerf'], ['win7'], _TESTS)
    testing_common.AddTests(['ChromiumPerf'], ['win7'], _REF_TEST)

    trace_a = utils.TestKey('ChromiumPerf/win7/suite/graph_a/trace_a').get()
    trace_a_ref = utils.TestKey(
        'ChromiumPerf/win7/suite/graph_a/trace_a/ref').get()
    trace_b = utils.TestKey('ChromiumPerf/win7/suite/graph_b/trace_b').get()
    suite = utils.TestKey('ChromiumPerf/win7/suite').get()
    trace_a_test_container_key = utils.GetTestContainerKey(trace_a)
    trace_a_ref_test_container_key = utils.GetTestContainerKey(trace_a_ref)
    trace_b_test_container_key = utils.GetTestContainerKey(trace_b)

    now = datetime.datetime.now()
    deprecated_time = datetime.datetime.now() - datetime.timedelta(days=20)

    for i in range(0, 5):
      graph_data.Row(
          id=i, value=(i * 100), parent=trace_a_test_container_key,
          timestamp=deprecated_time).put()
      graph_data.Row(
          id=i, value=i * 100, parent=trace_b_test_container_key,
          timestamp=(now if i == 4 else deprecated_time)).put()
      graph_data.Row(
          id=i, value=(i * 100), parent=trace_a_ref_test_container_key,
          timestamp=deprecated_time).put()

    return trace_a, trace_a_ref, trace_b, suite

  def _AddMockDataForDeletedTests(self):
    """Adds some sample data, some of which only has old timestamps."""
    testing_common.AddTests(['ChromiumPerf'], ['mac'], _TESTS)

    trace_a = utils.TestKey('ChromiumPerf/mac/suite/graph_a/trace_a').get()
    trace_b = utils.TestKey('ChromiumPerf/mac/suite/graph_b/trace_b').get()
    suite = utils.TestKey('ChromiumPerf/mac/suite').get()
    trace_a_test_container_key = utils.GetTestContainerKey(trace_a)
    trace_b_test_container_key = utils.GetTestContainerKey(trace_b)

    now = datetime.datetime.now()
    deleted_time = datetime.datetime.now() - datetime.timedelta(days=200)

    for i in range(0, 5):
      graph_data.Row(
          id=i, value=(i * 100), parent=trace_a_test_container_key,
          timestamp=deleted_time).put()
      graph_data.Row(
          id=i, value=i * 100, parent=trace_b_test_container_key,
          timestamp=(now if i == 4 else deleted_time)).put()

    return trace_a, trace_b, suite

  def testDeprecateTestsMapper_UpdatesTest(self):
    trace_a, _, trace_b, suite = self._AddMockDataForDeprecatedTests()

    for operation in mr.DeprecateTestsMapper(trace_a):
      self._ExecOperation(operation)
    for operation in mr.DeprecateTestsMapper(trace_b):
      self._ExecOperation(operation)

    self.assertTrue(trace_a.deprecated)
    self.assertFalse(trace_b.deprecated)
    self.assertFalse(suite.deprecated)

  def testDeprecateTestsMapper_AllSubtestsDeprecated_UpdatesSuite(self):
    (trace_a, trace_a_ref, trace_b, suite) = (
        self._AddMockDataForDeprecatedTests())
    last_b = graph_data.Row.query(
        graph_data.Row.parent_test == utils.OldStyleTestKey(trace_b.key),
        graph_data.Row.revision == 4).get()
    last_b.timestamp = datetime.datetime.now() - datetime.timedelta(days=20)
    last_b.put()

    for operation in mr.DeprecateTestsMapper(trace_a):
      self._ExecOperation(operation)
    for operation in mr.DeprecateTestsMapper(trace_a_ref):
      self._ExecOperation(operation)
    for operation in mr.DeprecateTestsMapper(trace_b):
      self._ExecOperation(operation)

    self.assertTrue(trace_a.deprecated)
    self.assertTrue(trace_b.deprecated)
    self.assertTrue(suite.deprecated)

  def testDeprecateTestsMapper_DeletesTest(self):
    trace_a, trace_b, suite = self._AddMockDataForDeletedTests()
    trace_a_key = trace_a.key
    trace_b_key = trace_b.key
    suite_key = suite.key

    for operation in mr.DeprecateTestsMapper(trace_a):
      self._ExecOperation(operation)
    for operation in mr.DeprecateTestsMapper(trace_b):
      self._ExecOperation(operation)
    self.ExecuteTaskQueueTasks(
        '/delete_test_data', mr._DELETE_TASK_QUEUE_NAME)

    self.assertIsNone(trace_a_key.get())
    self.assertIsNotNone(trace_b_key.get())
    self.assertIsNotNone(suite_key.get())

  def _AddMockDataForTestingUnits(self, with_units):
    """Adds a sample anomaly with or without units.

    Args:
      with_units: Boolean specifying if the anomaly.test should have units.
    """
    testing_common.AddTests(['ChromiumPerf'], ['mac'], _TESTS)
    test_row = utils.TestMetadataKey(
        'ChromiumPerf/mac/suite/graph_a/trace_a').get()

    # Test row must have units.
    if with_units:
      test_row.units = 'ms'
    test_row.put()

    anomaly_row = anomaly.Anomaly(
        start_revision=12345,
        end_revision=12355,
        test=test_row.key).put()

    return anomaly_row

  def testUnitsIntoAnomaly(self):
    anomaly_row = self._AddMockDataForTestingUnits(True)
    self.assertEqual(anomaly_row.get().test.get().units, 'ms')
    self.assertIsNone(anomaly_row.get().units)

    for operation in mr.StoreUnitsInAnomalyEntity(anomaly_row.get()):
      self._ExecOperation(operation)

    self.assertEqual(anomaly_row.get().units, 'ms')


  def testUnitsIntoAnomaly_noUnitsInTest(self):
    anomaly_row = self._AddMockDataForTestingUnits(False)
    self.assertIsNone(anomaly_row.get().test.get().units)
    self.assertIsNone(anomaly_row.get().units)

    for operation in mr.StoreUnitsInAnomalyEntity(anomaly_row.get()):
      self._ExecOperation(operation)

    self.assertIsNone(anomaly_row.get().units)

if __name__ == '__main__':
  unittest.main()
