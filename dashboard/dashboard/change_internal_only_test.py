# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import change_internal_only
from dashboard.common import testing_common
from dashboard.models import anomaly
from dashboard.models import graph_data


class ChangeInternalOnlyTest(testing_common.TestCase):

  def testUpdateBots(self):
    testing_common.AddTests(
        ['ChromiumPerf', 'ChromiumGPU'],
        ['win7', 'mac'],
        {'scrolling': {'first_paint': {}}})
    for key in graph_data.TestMetadata.query().fetch(keys_only=True):
      anomaly.Anomaly(
          test=key, start_revision=15001, end_revision=15005,
          median_before_anomaly=100, median_after_anomaly=200).put()

    internal_master_bots = [
        ('ChromiumPerf', 'win7'),
        ('ChromiumGPU', 'mac'),
    ]
    change_internal_only.UpdateBots(internal_master_bots, True)
    self.PatchDatastoreHooksRequest()
    self.ExecuteDeferredTasks(change_internal_only.QUEUE_NAME)

    for bot in graph_data.Bot.query().fetch():
      master_name = bot.key.parent().id()
      bot_name = bot.key.id()
      expected = (master_name, bot_name) in internal_master_bots
      self.assertEqual(expected, bot.internal_only)

      query = graph_data.TestMetadata.query(
          graph_data.TestMetadata.master_name == master_name,
          graph_data.TestMetadata.bot_name == bot_name)
      for test in query.fetch():
        self.assertEqual(expected, test.internal_only)

        anomalies, _, _ = anomaly.Anomaly.QueryAsync(
            test=test.test_path).get_result()
        for alert in anomalies:
          self.assertEqual(expected, alert.internal_only)


if __name__ == '__main__':
  unittest.main()
