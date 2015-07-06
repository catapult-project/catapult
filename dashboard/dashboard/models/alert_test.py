# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for alert module."""

import unittest

from dashboard import testing_common
from dashboard import utils
from dashboard.models import alert
from dashboard.models import anomaly


class AlertTest(testing_common.TestCase):
  """Test case for some functions in anomaly."""

  def _AddDataForTests(self):
    testing_common.AddDataToMockDataStore(
        ['SuperGPU'], ['Bot1', 'Bot2', 'Bot3'], {'foo': {'bar': {}}})

  def testGetBotNamesFromAlerts_EmptyList_ReturnsEmptySet(self):
    """Tests that an empty set is returned when nothing is passed."""
    self.assertEqual(set(), alert.GetBotNamesFromAlerts([]))

  def testGetBotNamesFromAlerts_RemovesDuplicates(self):
    """Tests that duplicates are removed from the result."""
    self._AddDataForTests()
    test_key_1 = utils.TestKey('SuperGPU/Bot1/foo/bar')
    anomaly.Anomaly(test=test_key_1).put()
    anomaly.Anomaly(test=test_key_1).put()
    anomalies = anomaly.Anomaly.query().fetch()
    bot_names = alert.GetBotNamesFromAlerts(anomalies)
    self.assertEqual(2, len(anomalies))
    self.assertEqual(1, len(bot_names))

  def testGetBotNamesFromAlerts_TypicalCase(self):
    """Tests that we can get the name of the bots for a list of anomalies."""
    self._AddDataForTests()
    test_key_1 = utils.TestKey('SuperGPU/Bot1/foo/bar')
    test_key_2 = utils.TestKey('SuperGPU/Bot2/foo/bar')
    test_key_3 = utils.TestKey('SuperGPU/Bot3/foo/bar')
    anomaly.Anomaly(test=test_key_1).put()
    anomaly.Anomaly(test=test_key_2).put()
    anomaly.Anomaly(test=test_key_3).put()
    anomalies = anomaly.Anomaly.query().fetch()
    bot_names = alert.GetBotNamesFromAlerts(anomalies)
    self.assertEqual({'Bot1', 'Bot2', 'Bot3'}, bot_names)


if __name__ == '__main__':
  unittest.main()
