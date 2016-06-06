# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb

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

  def testGetTestMetadataKey_Test(self):
    a = anomaly.Anomaly(
        test=ndb.Key('Master', 'm', 'Bot', 'b', 'Test', 't', 'Test', 't'))
    k = a.GetTestMetadataKey()
    self.assertEqual('TestMetadata', k.kind())
    self.assertEqual('m/b/t/t', k.id())
    self.assertEqual('m/b/t/t', utils.TestPath(k))

  def testGetTestMetadataKey_TestMetadata(self):
    a = anomaly.Anomaly(test=utils.TestKey('a/b/c/d'))
    k = a.GetTestMetadataKey()
    self.assertEqual('TestMetadata', k.kind())
    self.assertEqual('a/b/c/d', k.id())
    self.assertEqual('a/b/c/d', utils.TestPath(k))

  def testGetTestMetadataKey_None(self):
    a = anomaly.Anomaly()
    k = a.GetTestMetadataKey()
    self.assertIsNone(k)

  def testGetAlertsForTest(self):
    old_style_key1 = utils.OldStyleTestKey('master/bot/test1/metric')
    new_style_key1 = utils.TestMetadataKey('master/bot/test1/metric')
    old_style_key2 = utils.OldStyleTestKey('master/bot/test2/metric')
    new_style_key2 = utils.TestMetadataKey('master/bot/test2/metric')
    anomaly.Anomaly(id="old_1", test=old_style_key1).put()
    anomaly.Anomaly(id="old_1a", test=old_style_key1).put()
    anomaly.Anomaly(id="old_2", test=old_style_key2).put()
    anomaly.Anomaly(id="new_1", test=new_style_key1).put()
    anomaly.Anomaly(id="new_2", test=new_style_key2).put()
    anomaly.Anomaly(id="new_2a", test=new_style_key2).put()
    key1_alerts = anomaly.Anomaly.GetAlertsForTest(new_style_key1)
    self.assertEqual(
        ['new_1', 'old_1', 'old_1a'], [a.key.id() for a in key1_alerts])
    key2_alerts = anomaly.Anomaly.GetAlertsForTest(old_style_key2)
    self.assertEqual(
        ['new_2', 'new_2a', 'old_2'], [a.key.id() for a in key2_alerts])
    key2_alerts_limit = anomaly.Anomaly.GetAlertsForTest(
        old_style_key2, limit=2)
    self.assertEqual(
        ['new_2', 'new_2a'], [a.key.id() for a in key2_alerts_limit])


if __name__ == '__main__':
  unittest.main()
