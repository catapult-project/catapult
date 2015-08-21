# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import testing_common
from dashboard import utils
from dashboard.models import alert
from dashboard.models import anomaly


class AlertTest(testing_common.TestCase):
  """Test case for some functions in anomaly."""

  def testGetBotNamesFromAlerts_EmptyList_ReturnsEmptySet(self):
    self.assertEqual(set(), alert.GetBotNamesFromAlerts([]))

  def testGetBotNamesFromAlerts_RemovesDuplicates(self):
    testing_common.AddTests(
        ['SuperGPU'], ['Bot1'], {'foo': {'bar': {}}})
    anomaly.Anomaly(test=utils.TestKey('SuperGPU/Bot1/foo/bar')).put()
    anomaly.Anomaly(test=utils.TestKey('SuperGPU/Bot1/foo/bar')).put()
    anomalies = anomaly.Anomaly.query().fetch()
    bot_names = alert.GetBotNamesFromAlerts(anomalies)
    self.assertEqual(2, len(anomalies))
    self.assertEqual(1, len(bot_names))

  def testGetBotNamesFromAlerts_ReturnsBotNames(self):
    testing_common.AddTests(
        ['SuperGPU'], ['Bot1', 'Bot2', 'Bot3'], {'foo': {'bar': {}}})
    anomaly.Anomaly(test=utils.TestKey('SuperGPU/Bot1/foo/bar')).put()
    anomaly.Anomaly(test=utils.TestKey('SuperGPU/Bot2/foo/bar')).put()
    anomaly.Anomaly(test=utils.TestKey('SuperGPU/Bot3/foo/bar')).put()
    anomalies = anomaly.Anomaly.query().fetch()
    bot_names = alert.GetBotNamesFromAlerts(anomalies)
    self.assertEqual({'Bot1', 'Bot2', 'Bot3'}, bot_names)


if __name__ == '__main__':
  unittest.main()
