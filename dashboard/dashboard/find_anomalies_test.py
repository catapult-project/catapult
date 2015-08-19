# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for find_anomalies module."""

import sys
import unittest

import mock

from dashboard import find_anomalies
from dashboard import find_change_points
from dashboard import testing_common
from dashboard import utils
from dashboard.models import anomaly
from dashboard.models import graph_data
from dashboard.models import sheriff

# Sample time series.
_TEST_ROW_DATA = [
    (241105, 2126.75), (241116, 2140.375), (241151, 2149.125),
    (241154, 2147.25), (241156, 2130.625), (241160, 2136.25),
    (241188, 2146.75), (241201, 2141.875), (241226, 2160.625),
    (241247, 2108.125), (241249, 2134.25), (241254, 2130.0),
    (241262, 2126.0), (241268, 2142.625), (241271, 2129.125),
    (241282, 2166.625), (241294, 2125.375), (241298, 2155.5),
    (241303, 2158.5), (241317, 2146.25), (241323, 2123.375),
    (241330, 2121.5), (241342, 2151.25), (241355, 2155.25),
    (241371, 2136.375), (241386, 2154.0), (241405, 2118.125),
    (241420, 2157.625), (241432, 2140.75), (241441, 2132.25),
    (241452, 2138.25), (241455, 2119.375), (241471, 2134.0),
    (241488, 2127.25), (241503, 2162.5), (241520, 2116.375),
    (241524, 2139.375), (241529, 2143.5), (241532, 2141.5),
    (241535, 2147.0), (241537, 2184.125), (241546, 2180.875),
    (241553, 2181.5), (241559, 2176.875), (241566, 2164.0),
    (241577, 2182.875), (241579, 2194.875), (241582, 2200.5),
    (241584, 2163.125), (241609, 2178.375), (241620, 2178.125),
    (241645, 2190.875), (241653, 2147.75), (241666, 2185.375),
    (241697, 2173.875), (241716, 2172.125), (241735, 2172.5),
    (241757, 2154.75), (241766, 2196.75), (241782, 2184.125),
    (241795, 2191.5)
]


def _MakeSampleChangePoint(x_value, median_before, median_after):
  """Makes a sample find_change_points.ChangePoint for use in these tests."""
  # The only thing that matters in these tests is the revision number
  # and the values before and after.
  return find_change_points.ChangePoint(
      x_value=x_value,
      median_before=median_before,
      median_after=median_after,
      window_start=1,
      window_end=8,
      size_before=None,
      size_after=None,
      relative_change=None,
      std_dev_before=None,
      t_statistic=None,
      degrees_of_freedom=None,
      p_value=None)


class EndRevisionMatcher(object):
  """Custom matcher to test if an anomaly matches a given end rev."""

  def __init__(self, end_revision):
    """Initializes with the end time to check."""
    self._end_revision = end_revision

  def __eq__(self, rhs):
    """Checks to see if RHS has the same end time."""
    return self._end_revision == rhs.end_revision

  def __repr__(self):
    """Shows a readable revision which can be printed when assert fails."""
    return '<IsEndRevision %d>' % self._end_revision


class ModelMatcher(object):
  """Custom matcher to check if two ndb entity names match."""

  def __init__(self, name):
    """Initializes with the name of the entity."""
    self._name = name

  def __eq__(self, rhs):
    """Checks to see if RHS has the same name."""
    return rhs.key.string_id() == self._name

  def __repr__(self):
    """Shows a readable revision which can be printed when assert fails."""
    return '<IsModel %s>' % self._name


class ProcessAlertsTest(testing_common.TestCase):

  def setUp(self):
    super(ProcessAlertsTest, self).setUp()
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def _AddDataForTests(self):
    testing_common.AddTests(
        ['ChromiumGPU'],
        ['linux-release'], {
            'scrolling_benchmark': {
                'ref': {},
            },
        })
    ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    for i in range(9000, 10070, 5):
      # Internal-only data should be found.
      test_container_key = utils.GetTestContainerKey(ref.key)
      graph_data.Row(
          id=i + 1, value=float(i * 3),
          parent=test_container_key, internal_only=True).put()

  @mock.patch.object(
      find_anomalies.find_change_points, 'FindChangePoints',
      mock.MagicMock(return_value=[
          _MakeSampleChangePoint(10011, 50, 100),
          _MakeSampleChangePoint(10041, 200, 100),
          _MakeSampleChangePoint(10061, 0, 100),
      ]))
  @mock.patch.object(find_anomalies.email_sheriff, 'EmailSheriff')
  def testProcessTest(self, mock_email_sheriff):
    self._AddDataForTests()
    test_path = 'ChromiumGPU/linux-release/scrolling_benchmark/ref'
    test = utils.TestKey(test_path).get()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[test_path]).put()
    test.put()

    find_anomalies.ProcessTest(test.key)

    expected_calls = [
        mock.call(ModelMatcher('sheriff'),
                  ModelMatcher('ref'),
                  EndRevisionMatcher(10011)),
        mock.call(ModelMatcher('sheriff'),
                  ModelMatcher('ref'),
                  EndRevisionMatcher(10041)),
        mock.call(ModelMatcher('sheriff'),
                  ModelMatcher('ref'),
                  EndRevisionMatcher(10061))]
    self.assertEqual(expected_calls, mock_email_sheriff.call_args_list)

    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(anomalies), 3)

    def AnomalyExists(
        anomalies, test, percent_changed, direction,
        start_revision, end_revision, sheriff_name, internal_only):
      for a in anomalies:
        if (a.test == test and
            a.percent_changed == percent_changed and
            a.direction == direction and
            a.start_revision == start_revision and
            a.end_revision == end_revision and
            a.sheriff.string_id() == sheriff_name and
            a.internal_only == internal_only):
          return True
      return False

    self.assertTrue(
        AnomalyExists(
            anomalies, test.key, percent_changed=100, direction=anomaly.UP,
            start_revision=10007, end_revision=10011, sheriff_name='sheriff',
            internal_only=False))

    self.assertTrue(
        AnomalyExists(
            anomalies, test.key, percent_changed=-50, direction=anomaly.DOWN,
            start_revision=10037, end_revision=10041, sheriff_name='sheriff',
            internal_only=False))

    self.assertTrue(
        AnomalyExists(
            anomalies, test.key, percent_changed=sys.float_info.max,
            direction=anomaly.UP, start_revision=10057, end_revision=10061,
            sheriff_name='sheriff', internal_only=False))

    # This is here just to verify that AnomalyExists returns False sometimes.
    self.assertFalse(
        AnomalyExists(
            anomalies, test.key, percent_changed=100, direction=anomaly.DOWN,
            start_revision=10037, end_revision=10041, sheriff_name='sheriff',
            internal_only=False))

  @mock.patch.object(
      find_anomalies.find_change_points, 'FindChangePoints',
      mock.MagicMock(return_value=[
          _MakeSampleChangePoint(10011, 100, 50)
      ]))
  def testProcessTest_DownImprovementDirection_IsImprovementPropertySet(self):
    """Tests the Anomaly improvement direction when lower is better."""
    self._AddDataForTests()
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[test.test_path]).put()
    test.improvement_direction = anomaly.DOWN
    test.put()
    find_anomalies.ProcessTest(test.key)
    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(anomalies), 1)
    self.assertTrue(anomalies[0].is_improvement)

  @mock.patch('logging.error')
  def testProcessTest_NoSheriff_ErrorLogged(self, mock_logging_error):
    self._AddDataForTests()
    ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    find_anomalies.ProcessTest(ref.key)
    mock_logging_error.assert_called_with('No sheriff for %s', ref.key)

  @mock.patch.object(
      find_anomalies.find_change_points, 'FindChangePoints',
      mock.MagicMock(return_value=[
          _MakeSampleChangePoint(10026, 55.2, 57.8),
          _MakeSampleChangePoint(10041, 45.2, 37.8),
      ]))
  @mock.patch.object(find_anomalies.email_sheriff, 'EmailSheriff')
  def testProcessTest_FiltersOutImpovements(self, mock_email_sheriff):
    self._AddDataForTests()
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[test.test_path]).put()
    test.improvement_direction = anomaly.UP
    test.put()
    find_anomalies.ProcessTest(test.key)
    mock_email_sheriff.assert_called_once_with(
        ModelMatcher('sheriff'), ModelMatcher('ref'), EndRevisionMatcher(10041))

  @mock.patch.object(
      find_anomalies.find_change_points, 'FindChangePoints',
      mock.MagicMock(return_value=[
          _MakeSampleChangePoint(10011, 50, 100),
      ]))
  @mock.patch.object(find_anomalies.email_sheriff, 'EmailSheriff')
  def testProcessTest_InternalOnlyTest(self, mock_email_sheriff):
    """Verifies that internal-only tests are processed."""
    self._AddDataForTests()
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    test.internal_only = True
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[test.test_path]).put()
    test.put()

    find_anomalies.ProcessTest(test.key)
    expected_calls = [
        mock.call(ModelMatcher('sheriff'),
                  ModelMatcher('ref'),
                  EndRevisionMatcher(10011))]
    self.assertEqual(expected_calls, mock_email_sheriff.call_args_list)

    anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(anomalies), 1)
    self.assertEqual(test.key, anomalies[0].test)
    self.assertEqual(100, anomalies[0].percent_changed)
    self.assertEqual(anomaly.UP, anomalies[0].direction)
    self.assertEqual(10007, anomalies[0].start_revision)
    self.assertEqual(10011, anomalies[0].end_revision)
    self.assertTrue(anomalies[0].internal_only)

  def testProcessTest_AnomaliesMatchRefSeries_NoAlertCreated(self):
    # Tests that a Anomaly entity is not created if both the test and its
    # corresponding ref build series have the same data.
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'], {
            'scrolling_benchmark': {'ref': {}},
        })
    ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    non_ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark').get()
    test_container_key = utils.GetTestContainerKey(ref.key)
    test_container_key_non_ref = utils.GetTestContainerKey(non_ref.key)
    for row in _TEST_ROW_DATA:
      graph_data.Row(id=row[0], value=row[1], parent=test_container_key).put()
      graph_data.Row(id=row[0], value=row[1],
                     parent=test_container_key_non_ref).put()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[non_ref.test_path]).put()
    ref.put()
    non_ref.put()
    find_anomalies.ProcessTest(non_ref.key)
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(0, len(new_anomalies))

  def testProcessTest_AnomalyDoesNotMatchRefSeries_AlertCreated(self):
    # Tests that an Anomaly entity is created when non-ref series goes up, but
    # the ref series stays flat.
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'], {
            'scrolling_benchmark': {'ref': {}},
        })
    ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    non_ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark').get()
    test_container_key = utils.GetTestContainerKey(ref.key)
    test_container_key_non_ref = utils.GetTestContainerKey(non_ref.key)
    for row in _TEST_ROW_DATA:
      graph_data.Row(id=row[0], value=2125.375, parent=test_container_key).put()
      graph_data.Row(id=row[0], value=row[1],
                     parent=test_container_key_non_ref).put()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[ref.test_path]).put()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[non_ref.test_path]).put()
    ref.put()
    non_ref.put()
    find_anomalies.ProcessTest(non_ref.key)
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(len(new_anomalies), 1)

  def testProcessTest_CreatesAnAnomaly(self):
    """Tests that a particular anomaly is created for a sample data series."""
    testing_common.AddTests(
        ['ChromiumGPU'], ['linux-release'], {
            'scrolling_benchmark': {'ref': {}},
        })
    ref = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    test_container_key = utils.GetTestContainerKey(ref.key)
    for row in _TEST_ROW_DATA:
      graph_data.Row(id=row[0], value=row[1], parent=test_container_key).put()
    sheriff.Sheriff(
        email='a@google.com', id='sheriff', patterns=[ref.test_path]).put()
    ref.put()
    find_anomalies.ProcessTest(ref.key)
    new_anomalies = anomaly.Anomaly.query().fetch()
    self.assertEqual(1, len(new_anomalies))
    self.assertEqual(anomaly.UP, new_anomalies[0].direction)
    self.assertEqual(241536, new_anomalies[0].start_revision)
    self.assertEqual(241537, new_anomalies[0].end_revision)

  @mock.patch('logging.error')
  def testProcessTest_LastAlertedRevisionTooHigh_PropertyReset(
      self, mock_logging_error):
    # If the last_alerted_revision property of the Test is too high,
    # then the property should be reset and an error should be logged.
    self._AddDataForTests()
    test = utils.TestKey(
        'ChromiumGPU/linux-release/scrolling_benchmark/ref').get()
    test.last_alerted_revision = 1234567890
    test.put()
    find_anomalies.ProcessTest(test.key)
    self.assertIsNone(test.key.get().last_alerted_revision)
    calls = [
        mock.call(
            'last_alerted_revision %d is higher than highest rev %d for test '
            '%s; setting last_alerted_revision to None.',
            1234567890,
            10066,
            'ChromiumGPU/linux-release/scrolling_benchmark/ref'),
        mock.call(
            'No rows fetched for %s',
            'ChromiumGPU/linux-release/scrolling_benchmark/ref')
    ]
    mock_logging_error.assert_has_calls(calls, any_order=True)


if __name__ == '__main__':
  unittest.main()
